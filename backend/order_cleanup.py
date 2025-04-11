import os
import json
import boto3
import time
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE")
logger.info(f"Using orders table from environment: {orders_table_name}")
table = dynamodb.Table(orders_table_name)

def handler(event, context):
    """
    Cleans up abandoned checkout sessions
    This function is designed to run on a schedule (e.g., every 15 minutes)
    """
    logger.info("Starting abandoned checkout cleanup")
    
    current_time = int(time.time())
    # Find orders that have expired (older than 15 minutes and still PENDING)
    try:
        # Note: In a production environment, you would use a GSI or scan with filter
        # for better performance on large tables
        response = table.scan(
            FilterExpression="expires_at < :now AND status = :status",
            ExpressionAttributeValues={
                ":now": current_time,
                ":status": "PENDING"
            }
        )
        
        expired_orders = response.get("Items", [])
        logger.info(f"Found {len(expired_orders)} expired checkout sessions")
        
        # Mark each expired order
        for order in expired_orders:
            order_id = order.get("order_id")
            if not order_id:
                continue
                
            logger.info(f"Marking expired order: {order_id}")
            
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET status = :status, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "EXPIRED",
                    ":time": current_time
                }
            )
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": f"Cleaned up {len(expired_orders)} expired checkout sessions"
            })
        }
    except Exception as e:
        logger.error(f"Error during checkout cleanup: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": f"Failed to clean up expired sessions: {str(e)}"
            })
        } 