import os
import json
import boto3
import logging

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ORDERS_TABLE"))
ses = boto3.client("ses")

def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    order_id = body.get("reference")
    shipping_status = body.get("status")

    # Update the order's shipping status in DynamoDB
    table.update_item(
        Key={"order_id": order_id},
        UpdateExpression="SET shipping_status = :s",
        ExpressionAttributeValues={":s": shipping_status}
    )

    # Retrieve the customer email for notification
    order = table.get_item(Key={"order_id": order_id}).get("Item", {})
    customer_email = order.get("customer_email")
    
    if customer_email:
        ses.send_email(
            Source=os.environ.get("EMAIL_SENDER"),
            Destination={"ToAddresses": [customer_email]},
            Message={
                "Subject": {"Data": "Your Order Shipping Update"},
                "Body": {"Text": {"Data": f"Your order {order_id} status has been updated to: {shipping_status}."}}
            }
        )
        logging.info(f"Email notification sent to {customer_email} for order {order_id}")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Prodigi webhook processed"})
    } 