import os
import json
import stripe
import boto3
from decimal import Decimal
import logging
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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

# Email configuration
EMAIL_SENDER = os.environ.get("EMAIL_SENDER")
NOTIFICATION_EMAIL = "hello@hansenhome.ai"

def send_notification_email(order_data, payment_intent):
    """Send an email notification about a new purchase"""
    if not EMAIL_SENDER:
        logger.warning("No EMAIL_SENDER configured, skipping notification")
        return
    
    try:
        # Extract order details
        order_id = order_data.get('order_id', 'Unknown')
        customer_email = payment_intent.get('receipt_email', 'Unknown')
        amount = payment_intent.get('amount', 0)
        # Convert amount from cents to dollars with proper formatting
        amount_formatted = f"${(amount / 100):.2f}"
        
        # Get items if available
        items = order_data.get('items', [])
        items_html = ""
        for item in items:
            name = item.get('name', 'Unknown item')
            qty = item.get('quantity', 1)
            price = item.get('price', 0)
            items_html += f"<li>{name} x {qty} - ${price}</li>"
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"New Order: {order_id}"
        msg['From'] = EMAIL_SENDER
        msg['To'] = NOTIFICATION_EMAIL
        
        # Create HTML version
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ padding: 20px; }}
                h2 {{ color: #256F8A; }}
                .order-details {{ margin: 20px 0; }}
                .order-total {{ font-weight: bold; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>New Order Received!</h2>
                <p>A new order has been placed and payment has been confirmed.</p>
                
                <div class="order-details">
                    <p><strong>Order ID:</strong> {order_id}</p>
                    <p><strong>Customer Email:</strong> {customer_email}</p>
                    <p><strong>Total Amount:</strong> {amount_formatted}</p>
                </div>
                
                <h3>Order Items:</h3>
                <ul>
                    {items_html}
                </ul>
                
                <p class="order-total">Total: {amount_formatted}</p>
                
                <p>This order is being processed for fulfillment through Prodigi.</p>
            </div>
        </body>
        </html>
        """
        
        # Create plain text version
        text = f"""
        New Order Received!
        
        A new order has been placed and payment has been confirmed.
        
        Order ID: {order_id}
        Customer Email: {customer_email}
        Total Amount: {amount_formatted}
        
        This order is being processed for fulfillment through Prodigi.
        """
        
        # Attach parts
        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))
        
        # Send email
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_SENDER, os.environ.get('EMAIL_PASSWORD', ''))
            server.send_message(msg)
            
        logger.info(f"Notification email sent for order {order_id}")
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")

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
            # Get the current order first
            get_response = table.get_item(Key={"order_id": order_id})
            current_order = get_response.get("Item", {})
            
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
            
            # Send email notification
            send_notification_email(current_order, payment_intent)
            
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
            
            # Try to update the client's browser by posting to our webhook-status resource
            try:
                public_webhook_url = os.environ.get("PUBLIC_WEBHOOK_URL")
                if public_webhook_url and client_id:
                    # This is used by the frontend to poll for status updates
                    status_data = {
                        "clientId": client_id,
                        "orderId": order_id,
                        "status": "PAYMENT_COMPLETE",
                        "timestamp": current_time
                    }
                    
                    # Store this status update for the frontend to poll
                    # This is necessary because we can't push directly to the browser
                    table.put_item(
                        Item={
                            "status_update_id": f"{client_id}_{current_time}",
                            "client_id": client_id,
                            "order_id": order_id,
                            "status": "PAYMENT_COMPLETE",
                            "timestamp": current_time,
                            "expires_at": current_time + (60 * 60 * 24)  # 24 hour TTL
                        }
                    )
                    
                    logger.info(f"Stored status update for client: {client_id}")
            except Exception as status_err:
                logger.error(f"Error updating client status: {str(status_err)}")
                # This is non-critical, so we continue processing
                
        except Exception as e:
            logger.error(f"Error updating order status: {str(e)}")
            return {"statusCode": 500, "body": json.dumps({"error": f"Error processing payment: {str(e)}"})}

    return {"statusCode": 200, "body": json.dumps({"received": True})} 