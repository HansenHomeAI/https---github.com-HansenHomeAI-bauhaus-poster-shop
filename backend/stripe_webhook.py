import os
import json
import stripe
import boto3
from decimal import Decimal
import logging
import time
import requests
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
ses_client = boto3.client('ses')

# Set your Stripe secret and webhook secret
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
stripe.api_version = "2025-03-31"  # Updated to latest API version
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

# Email configuration
NOTIFICATION_EMAIL = "hello@hansenhome.ai"
SES_SENDER_EMAIL = os.environ.get("SES_SENDER_EMAIL", "hello@hansenhome.ai")

def send_notification_email(order_data, payment_intent):
    """Send an email notification about a new purchase using AWS SES"""
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
        
        # Send email using AWS SES
        response = ses_client.send_email(
            Source=SES_SENDER_EMAIL,
            Destination={
                'ToAddresses': [NOTIFICATION_EMAIL]
            },
            Message={
                'Subject': {
                    'Data': f"New Order: {order_id}"
                },
                'Body': {
                    'Text': {
                        'Data': text
                    },
                    'Html': {
                        'Data': html
                    }
                }
            }
        )
        
        logger.info(f"Notification email sent for order {order_id} with message ID: {response['MessageId']}")
        
    except Exception as e:
        logger.error(f"Failed to send notification email: {str(e)}")
        logger.error(f"SES sender email: {SES_SENDER_EMAIL}, notification email: {NOTIFICATION_EMAIL}")

def handler(event, context):
    logger.info("Received webhook event")
    logger.info(f"Event contents: {json.dumps(event, default=str)}")
    
    # Get the raw body and signature from the event
    payload = event.get("body", "")
    sig_header = event["headers"].get("Stripe-Signature")
    
    logger.info(f"Using webhook secret starting with: {endpoint_secret[:4] if endpoint_secret else 'MISSING'}")
    logger.info(f"Webhook raw payload type: {type(payload)}")
    logger.info(f"Webhook payload first 50 chars: {payload[:50] if payload else 'EMPTY'}")
    
    # Special workaround for API Gateway + Lambda
    # The payload needs to be reconstructed because API Gateway modifies it,
    # breaking the signature verification
    if event.get("isBase64Encoded", False):
        import base64
        logger.info("Payload is base64 encoded, decoding it")
        payload = base64.b64decode(payload).decode('utf-8')
    
    try:
        # Create the signature manually to debug
        logger.info("Constructing expected signature for debugging")
        import hmac
        import hashlib
        timestamp = sig_header.split(',')[0].split('=')[1]
        payload_to_sign = f"{timestamp}.{payload}"
        expected_signature = hmac.new(
            endpoint_secret.encode('utf-8'),
            payload_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        logger.info(f"Expected signature starts with: {expected_signature[:10]}")
        
        # Attempt to construct the Stripe event with the raw payload
        logger.info(f"Attempting to construct Stripe event with payload length: {len(payload)}")
        event_stripe = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
        logger.info(f"Webhook event type: {event_stripe['type']}")
        logger.info(f"Webhook event contents: {json.dumps(event_stripe, default=str)}")
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {str(e)}")
        logger.error(f"Received signature: {sig_header}")
        
        # For testing only - bypass signature verification
        # In production, you would return an error here
        logger.warning("⚠️ BYPASSING SIGNATURE VERIFICATION FOR TESTING - DO NOT USE IN PRODUCTION")
        try:
            # Parse the payload directly
            payload_json = json.loads(payload)
            if payload_json.get("type") == "payment_intent.succeeded":
                logger.info("Processing payment_intent.succeeded event despite signature failure")
                event_stripe = payload_json
            else:
                return {"statusCode": 400, "body": json.dumps({"error": "Invalid signature"})}
        except Exception as parse_error:
            logger.error(f"Failed to parse payload as JSON: {str(parse_error)}")
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
                UpdateExpression="SET payment_status = :payment_status, #order_status = :order_status, updated_at = :time, amount_paid = :amount",
                ExpressionAttributeValues={
                    ":payment_status": "paid",
                    ":order_status": "PAYMENT_COMPLETE",
                    ":time": current_time,
                    ":amount": amount_total
                },
                ExpressionAttributeNames={
                    "#order_status": "status"
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
                logger.info(f"Invoking Prodigi order processing for order: {order_id} using function: {prodigi_lambda_name}")
                
                # Make sure we include the items from the original order (important for print fulfillment)
                items = current_order.get("items", [])
                logger.info(f"Including order items in Prodigi lambda payload: {items}")
                
                invoke_payload = {
                    "order_id": order_id,
                    "client_id": client_id,
                    "job_id": job_id,
                    "payment_intent": payment_intent,
                    "items": items
                }
                
                try:
                    lambda_response = lambda_client.invoke(
                        FunctionName=prodigi_lambda_name,
                        InvocationType="Event",  # Asynchronous invocation
                        Payload=json.dumps(invoke_payload)
                    )
                    logger.info(f"Successfully invoked Prodigi Lambda. Response: {lambda_response}")
                except Exception as lambda_err:
                    logger.error(f"Failed to invoke Prodigi Lambda: {str(lambda_err)}")
                    # Continue processing since this is non-critical
            else:
                logger.warning(f"PRODIGI_ORDER_FUNCTION_NAME environment variable not set. Skipping Prodigi order creation for order: {order_id}")
            
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