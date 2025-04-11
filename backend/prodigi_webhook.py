import os
import json
import boto3
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE")
logger.info(f"Using orders table from environment: {orders_table_name}")
table = dynamodb.Table(orders_table_name)
ses = boto3.client("ses")

def handler(event, context):
    logger.info(f"Received Prodigi webhook event: {event}")
    body = json.loads(event.get("body", "{}"))
    order_id = body.get("reference")
    shipping_status = body.get("status")
    
    if not order_id:
        logger.error("No order reference provided in webhook")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing order reference"})
        }

    logger.info(f"Processing webhook for order {order_id} with status {shipping_status}")
    
    # Update the order's shipping status in DynamoDB
    try:
        table.update_item(
            Key={"order_id": order_id},
            UpdateExpression="SET shipping_status = :s",
            ExpressionAttributeValues={":s": shipping_status}
        )
        logger.info(f"Updated order {order_id} status to {shipping_status}")
    except Exception as e:
        logger.error(f"Error updating order status in DynamoDB: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Failed to update order: {str(e)}"})
        }

    # Retrieve the customer email for notification
    try:
        response = table.get_item(Key={"order_id": order_id})
        order = response.get("Item", {})
        customer_email = order.get("customer_email")
        
        if customer_email:
            ses_sender = os.environ.get("SES_SENDER_EMAIL", "hello@hansenhome.ai")
            logger.info(f"Sending notification to {customer_email} from {ses_sender}")
            
            ses.send_email(
                Source=ses_sender,
                Destination={"ToAddresses": [customer_email]},
                Message={
                    "Subject": {"Data": "Your Order Shipping Update"},
                    "Body": {"Text": {"Data": f"Your order {order_id} status has been updated to: {shipping_status}."}}
                }
            )
            logger.info(f"Email notification sent to {customer_email} for order {order_id}")
        else:
            logger.warning(f"No customer email found for order {order_id}")
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        # Continue processing since email notification failure is not critical
    
    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Prodigi webhook processed successfully"})
    } 