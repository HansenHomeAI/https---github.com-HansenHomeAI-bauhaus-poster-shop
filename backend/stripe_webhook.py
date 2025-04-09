import os
import json
import stripe
import boto3
from decimal import Decimal
import logging

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ORDERS_TABLE"))
lambda_client = boto3.client("lambda")

# Set your Stripe secret and webhook secret
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
stripe.api_version = "2023-10-16"  # Use a stable API version that matches the frontend
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

def handler(event, context):
    payload = event.get("body", "")
    sig_header = event["headers"].get("Stripe-Signature")
    
    try:
        event_stripe = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except Exception as e:
        logging.error(f"Webhook signature verification failed: {str(e)}")
        return {"statusCode": 400, "body": "Webhook Error: Invalid signature"}

    if event_stripe["type"] == "checkout.session.completed":
        session = event_stripe["data"]["object"]
        order_id = session["metadata"]["order_id"]
        customer_email = session.get("customer_email")
        amount_total = session.get("amount_total")
        payment_status = session.get("payment_status")

        # Store order details in DynamoDB
        table.put_item(
            Item={
                "order_id": order_id,
                "stripe_session_id": session["id"],
                "customer_email": customer_email,
                "amount_total": Decimal(str(amount_total)),
                "payment_status": payment_status,
                "shipping_status": "pending"
            }
        )

        # Asynchronously invoke the Prodigi Order Lambda
        prodigi_lambda_name = os.environ.get("PRODIGI_ORDER_FUNCTION_NAME")
        invoke_payload = {
            "order_id": order_id,
            "stripe_session": session
        }
        lambda_client.invoke(
            FunctionName=prodigi_lambda_name,
            InvocationType="Event",
            Payload=json.dumps(invoke_payload)
        )
        logging.info(f"Order {order_id} stored and Prodigi order creation invoked.")

    return {"statusCode": 200, "body": "Webhook received"} 