import os
import json
import stripe
import uuid
import logging
import boto3
import time
from decimal import Decimal

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Stripe with your secret key
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "DEFAULT_NOT_SET")
# Log the first 8 characters of the secret key (safe to log part of it)
logger.info(f"Using Stripe secret key: {stripe_secret_key[:8]}...")

stripe.api_key = stripe_secret_key
# Use a stable API version that matches the frontend
stripe.api_version = "2025-03-31.basil"

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE", "SteepleCo-Orders")
try:
    orders_table = dynamodb.Table(orders_table_name)
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {str(e)}")
    # We'll still continue and handle this later if needed

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

def create_cors_response(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
            'Access-Control-Max-Age': '86400',
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
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
                'Access-Control-Max-Age': '86400',  # 24 hours
                'Content-Type': 'application/json'
            },
            'body': '{}'
        }

    try:
        # Log the incoming request details
        logger.info("Request headers: %s", event.get('headers', {}))
        logger.info("Request body: %s", event.get('body', '{}'))

        body = json.loads(event.get("body", "{}"))
        items = body.get("items", [])
        customer_email = body.get("customerEmail")
        client_id = body.get("clientId")
        shipping_details = body.get("shippingDetails", {})
        
        # Validate the input
        if not items:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No items provided'})
            }
        
        # Calculate amount in cents (Stripe requires amount in cents)
        amount = calculate_amount(items, shipping_details.get('shippingMethod', 'BUDGET'))
        
        # Generate a unique order ID
        order_id = str(uuid.uuid4())
        
        # Generate a unique job ID to track this checkout session
        job_id = str(uuid.uuid4())
        
        # Log checkout attempt
        logger.info(f"Creating checkout for email: {customer_email}, amount: {amount}, items: {json.dumps(items)}")
        
        # Create a temporary order record in DynamoDB
        timestamp = int(time.time())
        
        # Create order item for DynamoDB
        order_item = {
            'order_id': order_id,
            'job_id': job_id,
            'client_id': client_id,
            'status': 'PENDING',
            'customer_email': customer_email,
            'amount': amount,
            'items': json.dumps(items),
            'created_at': timestamp,
            'updated_at': timestamp,
            'expires_at': timestamp + 900  # 15-minute expiration
        }
        
        # Add shipping details if provided
        if shipping_details:
            order_item['shipping_details'] = shipping_details
        
        # Store the order in DynamoDB
        orders_table.put_item(Item=order_item)
        
        # Create a Stripe payment intent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='usd',
            receipt_email=customer_email,
            metadata={
                'order_id': order_id,
                'job_id': job_id,
                'client_id': client_id
            },
            payment_method_types=['card']
        )
        
        # Store the payment intent ID in the order
        orders_table.update_item(
            Key={'order_id': order_id},
            UpdateExpression="SET payment_intent_id = :pi",
            ExpressionAttributeValues={
                ':pi': payment_intent.id
            }
        )
        
        logger.info(f"Created payment intent: {payment_intent.id} for order: {order_id}")
        
        # Return the client secret to the frontend
        return {
            'statusCode': 200,
            'body': json.dumps({
                'clientSecret': payment_intent.client_secret,
                'orderId': order_id,
                'jobId': job_id,
                'clientId': client_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f"Failed to create checkout session: {str(e)}"})
        }

def calculate_amount(items, shipping_method):
    """Calculate the total amount in cents for Stripe"""
    # Calculate subtotal
    subtotal = 0
    for item in items:
        subtotal += float(item.get('price', 0)) * int(item.get('quantity', 1))
    
    # Add shipping cost
    shipping_cost = 0
    if shipping_method == 'STANDARD':
        shipping_cost = 5.80
    elif shipping_method == 'EXPRESS':
        shipping_cost = 15.30
    elif shipping_method == 'PRIORITY':
        shipping_cost = 27.30
    
    # Calculate total (convert to cents for Stripe)
    total = (subtotal + shipping_cost) * 100
    
    # Ensure we return an integer (Stripe requires integer amounts)
    return int(total) 