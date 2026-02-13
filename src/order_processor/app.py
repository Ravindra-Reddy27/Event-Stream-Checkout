import json
import os
import logging
import pymysql
import boto3
import datetime

# Configure Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SQS Client
sqs = boto3.client('sqs')
PROCESSED_QUEUE_URL = os.environ.get('PROCESSED_QUEUE_URL')

# Database Configuration (Loaded from Env Vars in Lambda)
DB_HOST = os.environ.get('DB_HOST')
DB_USER = os.environ.get('DB_USER')
DB_PASSWORD = os.environ.get('DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME')

def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=5
    )

def lambda_handler(event, context):
    """
    Triggered by SQS OrderCreated events.
    """
    conn = None
    try:
        conn = get_db_connection()
        
        for record in event['Records']:
            logger.info(f"Processing message ID: {record['messageId']}")
            body = json.loads(record['body'])
            process_order(conn, body)
            
    except Exception as e:
        logger.error(f"Critical Database Error: {str(e)}")
        # Raising the exception triggers SQS retry / DLQ logic
        raise e
    finally:
        if conn and conn.open:
            conn.close()

    return {"status": "success"}

def process_order(conn, order_data):
    order_id = order_data['order_id']
    customer_id = order_data['customer_id']
    items = order_data['items']
    
    try:
        with conn.cursor() as cursor:
            # 1. Start Transaction
            conn.begin()
            
            # 2. Insert Order as PENDING (Handle SQS duplicate messages for Idempotency)
            sql_insert_order = """
                INSERT IGNORE INTO orders (order_id, customer_id, items, status, created_at)
                VALUES (%s, %s, %s, 'PENDING', NOW())
            """
            cursor.execute(sql_insert_order, (order_id, customer_id, json.dumps(items)))
            
            # If rowcount is 0, the insert was ignored because the order already exists.
            if cursor.rowcount == 0:
                logger.info(f"Order {order_id} already exists. Skipping duplicate processing.")
                return # Exit early so we don't double-deduct inventory
            
            # 3. Check and Update Inventory
            inventory_sufficient = True
            
            for item in items:
                prod_id = item['product_id']
                qty_needed = item['quantity']
                
                # Check stock with FOR UPDATE to securely lock the row
                cursor.execute("SELECT quantity_available FROM inventory WHERE product_id = %s FOR UPDATE", (prod_id,))
                result = cursor.fetchone()
                
                if not result or result['quantity_available'] < qty_needed:
                    inventory_sufficient = False
                    logger.warning(f"Insufficient inventory for Product {prod_id} in Order {order_id}")
                    break
                
                # Decrement stock
                cursor.execute("UPDATE inventory SET quantity_available = quantity_available - %s WHERE product_id = %s", (qty_needed, prod_id))

            # 4. Finalize Transaction
            if inventory_sufficient:
                # Success: Mark PROCESSED
                cursor.execute("UPDATE orders SET status='PROCESSED', processed_at=NOW() WHERE order_id=%s", (order_id,))
                conn.commit()
                logger.info(f"Order {order_id} PROCESSED successfully.")
                
                # Publish Event to the next queue
                publish_processed_event(order_data)
                
            else:
                # Failure: Inventory is missing, we must rollback the partial changes
                conn.rollback() # This undoes the inventory changes AND the PENDING insert
                
                # Start a new transaction just to record the failure
                conn.begin() 
                sql_fail = """
                    INSERT INTO orders (order_id, customer_id, items, status, created_at, processed_at)
                    VALUES (%s, %s, %s, 'FAILED', NOW(), NOW())
                    ON DUPLICATE KEY UPDATE status='FAILED', processed_at=NOW()
                """
                cursor.execute(sql_fail, (order_id, customer_id, json.dumps(items)))
                conn.commit()
                logger.info(f"Order {order_id} successfully marked as FAILED in database.")

    except pymysql.MySQLError as e:
        conn.rollback()
        logger.error(f"SQL Error processing order {order_id}: {e}")
        raise e # Send to DLQ

def publish_processed_event(order_data):
    """
    Publish OrderProcessed event to the second SQS queue
    """
    try:
        event_payload = {
            'order_id': order_data['order_id'],
            'customer_id': order_data['customer_id'],
            'status': 'PROCESSED',
            'processed_at': datetime.datetime.utcnow().isoformat()
        }
        
        sqs.send_message(
            QueueUrl=PROCESSED_QUEUE_URL,
            MessageBody=json.dumps(event_payload)
        )
    except Exception as e:
        logger.error(f"Failed to publish processed event: {e}")