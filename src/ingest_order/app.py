import json
import uuid
import hashlib
import boto3
import os
import datetime
from botocore.exceptions import ClientError

# Initialize SQS client outside handler for connection reuse
sqs = boto3.client('sqs')
QUEUE_URL = os.environ.get('ORDER_QUEUE_URL')

def lambda_handler(event, context):
    """
    AWS Lambda Handler for POST /api/orders
    """
    try:
        # 1. Parse Body
        body = json.loads(event.get('body', '{}'))
        
        # 2. Input Validation (Using your excellent original logic)
        if not validate_input(body):
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Invalid input. Valid customer_id and items (>0 quantity) are required.'})
            }

        # 3. Generate Idempotent Order ID (Fix for Requirement 14)
        # We hash the exact payload. Same payload = same hash = same order_id.
        payload_string = json.dumps({"c": body['customer_id'], "i": body['items']}, sort_keys=True)
        hash_object = hashlib.md5(payload_string.encode('utf-8')).hexdigest()
        order_id = str(uuid.UUID(hash_object))
        
        # 4. Construct Event Payload
        order_event = {
            'order_id': order_id,
            'customer_id': body['customer_id'],
            'items': body['items'],
            'timestamp': datetime.datetime.utcnow().isoformat()
        }
        
        # 5. Publish to SQS 
        try:
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps(order_event)
            )
        except ClientError as e:
            print(f"Error sending message to SQS: {e}")
            return {
                'statusCode': 500,
                'body': json.dumps({'message': 'Internal Server Error'})
            }

        # 6. Return 202 Accepted 
        return {
            'statusCode': 202,
            'body': json.dumps({
                'message': 'Order accepted',
                'order_id': order_id
            })
        }

    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Invalid JSON format'})
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Internal Server Error'})
        }

def validate_input(body):
    """
    Validates that customer_id exists and items is a non-empty list.
    """
    if 'customer_id' not in body or not isinstance(body['customer_id'], str):
        return False
    if 'items' not in body or not isinstance(body['items'], list) or len(body['items']) == 0:
        return False
    
    # Validate individual items
    for item in body['items']:
        if 'product_id' not in item or 'quantity' not in item:
            return False
        if not isinstance(item['quantity'], int) or item['quantity'] <= 0:
            return False
            
    return True