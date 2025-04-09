import os
import json
import stripe
import boto3
from decimal import Decimal
import logging
import time

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE", "BauhausPosterShopOrders")
table = dynamodb.Table(orders_table_name)
lambda_client = boto3.client("lambda")

# Set your Stripe secret and webhook secret
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
stripe.api_version = "2023-10-16"  # Use a stable API version that matches the frontend
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

def handler(event, context):
    logger.info("Received webhook event")
    payload = event.get("body", "")
    sig_header = event["headers"].get("Stripe-Signature")
    
    try:
        event_stripe = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        logger.info(f"Webhook event type: {event_stripe['type']}")
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        return {"statusCode": 400, "body": json.dumps({"error": "Invalid signature"})}

    if event_stripe["type"] == "payment_intent.succeeded":
        payment_intent = event_stripe["data"]["object"]
        metadata = payment_intent.get("metadata", {})
        
        # Extract identifiers from metadata
        order_id = metadata.get("order_id")
        client_id = metadata.get("client_id")
        job_id = metadata.get("job_id")
        
        if not order_id:
            logger.error("Payment intent succeeded but no order_id in metadata")
            return {"statusCode": 400, "body": json.dumps({"error": "Missing order_id"})}
            
        logger.info(f"Processing successful payment for order: {order_id}, client: {client_id}, job: {job_id}")
        
        # Get customer details
        customer_email = payment_intent.get("receipt_email")
        amount_total = payment_intent.get("amount")
        
        current_time = int(time.time())
        
        try:
            # Update order status in DynamoDB
            update_response = table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET payment_status = :status, status = :order_status, updated_at = :time, amount_paid = :amount",
                ExpressionAttributeValues={
                    ":status": "paid",
                    ":order_status": "PAYMENT_COMPLETE",
                    ":time": current_time,
                    ":amount": amount_total
                },
                ReturnValues="ALL_NEW"
            )
            
            logger.info(f"Updated order status to PAYMENT_COMPLETE: {order_id}")
            
            # Get the updated order
            updated_order = update_response.get("Attributes", {})
            
            # Invoke order fulfillment Lambda asynchronously
            prodigi_lambda_name = os.environ.get("PRODIGI_ORDER_FUNCTION_NAME")
            if prodigi_lambda_name:
                logger.info(f"Invoking Prodigi order processing for order: {order_id}")
                
                invoke_payload = {
                    "order_id": order_id,
                    "client_id": client_id,
                    "job_id": job_id,
                    "payment_intent": payment_intent
                }
                
                lambda_client.invoke(
                    FunctionName=prodigi_lambda_name,
                    InvocationType="Event",  # Asynchronous invocation
                    Payload=json.dumps(invoke_payload)
                )
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            return {"statusCode": 500, "body": json.dumps({"error": f"Error processing payment: {str(e)}"})}

    return {"statusCode": 200, "body": json.dumps({"received": True})} 