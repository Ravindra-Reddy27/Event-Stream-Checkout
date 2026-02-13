import unittest
from unittest.mock import MagicMock, patch, call
import json
import os
import sys

# Ensure we can import the source code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Mock Environment Variables BEFORE importing the app
os.environ['PROCESSED_QUEUE_URL'] = 'https://sqs.mock-queue'
os.environ['DB_HOST'] = 'mock_host'
os.environ['DB_USER'] = 'mock_user'
os.environ['DB_PASSWORD'] = 'mock_pass'
os.environ['DB_NAME'] = 'mock_db'

from src.order_processor import app

class TestOrderProcessor(unittest.TestCase):

    @patch('src.order_processor.app.get_db_connection')
    @patch('src.order_processor.app.sqs')
    def test_process_order_success(self, mock_sqs, mock_get_db):
        """
        Test that a valid order updates inventory and sends a processed event.
        """
        # 1. Setup Mock DB Connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock Insert Success (rowcount=1 means new order)
        mock_cursor.rowcount = 1
        # Mock Inventory Check: Return 50 items available
        mock_cursor.fetchone.return_value = {'quantity_available': 50}

        # 2. Create a Dummy Event
        event = {
            'Records': [{
                'messageId': 'msg-123',
                'body': json.dumps({
                    'order_id': 'order-001',
                    'customer_id': 'cust-A',
                    'items': [{'product_id': 'prod-101', 'quantity': 1}]
                })
            }]
        }

        # 3. Run the Handler
        app.lambda_handler(event, None)

        # 4. Verify Logic
        # Ensure we used INSERT IGNORE for idempotency
        mock_cursor.execute.assert_any_call(
            """
                INSERT IGNORE INTO orders (order_id, customer_id, items, status, created_at)
                VALUES (%s, %s, %s, 'PENDING', NOW())
            """,
            ('order-001', 'cust-A', '[{"product_id": "prod-101", "quantity": 1}]')
        )

        # Ensure we decremented inventory
        mock_cursor.execute.assert_any_call(
            "UPDATE inventory SET quantity_available = quantity_available - %s WHERE product_id = %s",
            (1, 'prod-101')
        )
        
        # Ensure we marked order as PROCESSED
        mock_cursor.execute.assert_any_call(
            "UPDATE orders SET status='PROCESSED', processed_at=NOW() WHERE order_id=%s",
            ('order-001',)
        )
        
        # Ensure we committed the transaction and sent the message
        mock_conn.commit.assert_called()
        mock_sqs.send_message.assert_called()

    @patch('src.order_processor.app.get_db_connection')
    def test_process_order_insufficient_inventory(self, mock_get_db):
        """
        Test that low inventory triggers a rollback and records a FAILED status.
        """
        # 1. Setup Mock DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Mock Initial Insert Success
        mock_cursor.rowcount = 1
        # Mock Inventory Check: Return 0 items available
        mock_cursor.fetchone.return_value = {'quantity_available': 0}

        # 2. Create Dummy Event
        event = {
            'Records': [{
                'messageId': 'msg-456',
                'body': json.dumps({
                    'order_id': 'order-fail',
                    'customer_id': 'cust-B',
                    'items': [{'product_id': 'prod-101', 'quantity': 5}]
                })
            }]
        }

        # 3. Run Handler
        app.lambda_handler(event, None)

        # 4. Verify Logic
        # Ensure we ROLLED BACK the transaction after finding low stock
        mock_conn.rollback.assert_called()
        
        # Ensure we recorded the failure using the new INSERT/UPDATE logic
        # We use a specific multiline string check to match the app.py code
        mock_cursor.execute.assert_any_call(
            """
                    INSERT INTO orders (order_id, customer_id, items, status, created_at, processed_at)
                    VALUES (%s, %s, %s, 'FAILED', NOW(), NOW())
                    ON DUPLICATE KEY UPDATE status='FAILED', processed_at=NOW()
                """,
            ('order-fail', 'cust-B', '[{"product_id": "prod-101", "quantity": 5}]')
        )
        
        # Ensure the final commit for the FAILED status happened
        self.assertEqual(mock_conn.commit.call_count, 1)

if __name__ == '__main__':
    unittest.main()