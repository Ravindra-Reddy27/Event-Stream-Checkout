import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """
    Triggered by SQS OrderProcessed events.
    """
    for record in event['Records']:
        try:
            body = json.loads(record['body'])
            order_id = body.get('order_id')
            customer_id = body.get('customer_id')
            status = body.get('status')
            
            # Simulate sending a notification
            if status == 'PROCESSED':
                message = f"Notification sent for Order ID: {order_id} to Customer ID: {customer_id}"
                logger.info(message)
                print(message) # Prints to CloudWatch Logs
            
        except Exception as e:
            logger.error(f"Error processing notification: {e}")
            # We don't raise here because we don't want to retry malformed notifications infinitely
            
    return {"status": "success"}