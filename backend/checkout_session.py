import os
import json
import stripe
import uuid
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Stripe with your secret key
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
# Use a stable API version that matches the frontend
stripe.api_version = "2023-10-16"

def create_cors_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, Origin, X-Requested-With',
            'Access-Control-Max-Age': '3600',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body)
    }

def handler(event, context):
    logger.info("Received event: %s", json.dumps(event))
    
    # Handle CORS preflight request
    if event.get('httpMethod') == 'OPTIONS':
        logger.info("Handling OPTIONS request")
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '3600'
            },
            'body': ''
        }

    try:
        # Log the incoming request details
        logger.info("Request headers: %s", event.get('headers', {}))
        logger.info("Request body: %s", event.get('body', '{}'))

        body = json.loads(event.get("body", "{}"))
        items = body.get("items", [])
        customer_email = body.get("customerEmail")

        if not items:
            raise ValueError("No items provided in the request")

        # Calculate total amount
        total_amount = sum(int(float(item.get("price")) * 100) * item.get("quantity", 1) for item in items)

        # Create a PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency="usd",
            metadata={
                "order_id": str(uuid.uuid4())
            },
            receipt_email=customer_email,
            automatic_payment_methods={
                "enabled": True
            }
        )
        
        logger.info("Successfully created PaymentIntent: %s", payment_intent.id)
        
        return {
            "statusCode": 200,
            "headers": {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '3600',
                'Content-Type': 'application/json'
            },
            "body": json.dumps({
                "clientSecret": payment_intent.client_secret
            })
        }
    except Exception as e:
        logger.error("Error processing checkout: %s", str(e))
        return {
            "statusCode": 400,
            "headers": {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '3600',
                'Content-Type': 'application/json'
            },
            "body": json.dumps({"error": str(e)})
        } 