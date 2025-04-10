import os
import json
import stripe
import uuid
import logging
import boto3
import time

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Stripe with your secret key
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "DEFAULT_NOT_SET")
# Log the first 8 characters of the secret key (safe to log part of it)
logger.info(f"Using Stripe secret key: {stripe_secret_key[:8]}...")

stripe.api_key = stripe_secret_key
# Use a stable API version that matches the webhook configuration
stripe.api_version = "2025-03-31"

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE", "BauhausPosterShopOrders")
try:
    orders_table = dynamodb.Table(orders_table_name)
except Exception as e:
    logger.error(f"Failed to initialize DynamoDB table: {str(e)}")
    # We'll still continue and handle this later if needed

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
        
        # Extract client_id if provided or generate a new one
        client_id = body.get("clientId", str(uuid.uuid4()))
        
        # Generate a unique job ID for this checkout request
        job_id = str(uuid.uuid4())
        
        # Create a unique order ID
        order_id = str(uuid.uuid4())

        if not items:
            raise ValueError("No items provided in the request")

        # Calculate total amount
        total_amount = sum(int(float(item.get("price")) * 100) * item.get("quantity", 1) for item in items)
        
        logger.info(f"Creating checkout session for client_id: {client_id}, job_id: {job_id}, order_id: {order_id}")
        
        # Store the pending order in DynamoDB
        current_time = int(time.time())
        try:
            orders_table.put_item(
                Item={
                    'order_id': order_id,
                    'client_id': client_id,
                    'job_id': job_id,
                    'status': 'PENDING',
                    'items': json.dumps(items),  # Convert to string for DynamoDB
                    'customer_email': customer_email,
                    'amount': total_amount,
                    'created_at': current_time,
                    'updated_at': current_time,
                    'expires_at': current_time + 900  # 15 minutes expiration
                }
            )
            logger.info(f"Stored pending order in DynamoDB: {order_id}")
        except Exception as db_error:
            # Log error but continue - we can still create a PaymentIntent even if DB fails
            logger.error(f"Failed to store pending order in DynamoDB: {str(db_error)}")

        # Create a PaymentIntent with the order information in metadata
        logger.info(f"Creating PaymentIntent with amount: {total_amount}, using API version: {stripe.api_version}")
        payment_intent = stripe.PaymentIntent.create(
            amount=total_amount,
            currency="usd",
            metadata={
                "order_id": order_id,
                "client_id": client_id,
                "job_id": job_id
            },
            receipt_email=customer_email,
            automatic_payment_methods={
                "enabled": True
            },
            # Add idempotency key to prevent duplicate charges
            idempotency_key=job_id
        )
        
        logger.info(f"Successfully created PaymentIntent: {payment_intent.id} with client_secret starting with {payment_intent.client_secret[:15]}")
        
        # Update the order record with the PaymentIntent ID
        try:
            orders_table.update_item(
                Key={'order_id': order_id},
                UpdateExpression="SET payment_intent_id = :pi_id, updated_at = :time",
                ExpressionAttributeValues={
                    ':pi_id': payment_intent.id,
                    ':time': current_time
                }
            )
            logger.info(f"Updated order record with PaymentIntent ID: {payment_intent.id}")
        except Exception as db_error:
            logger.error(f"Failed to update order with PaymentIntent ID: {str(db_error)}")
        
        return {
            "statusCode": 200,
            "headers": {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
                'Access-Control-Max-Age': '86400',
                'Content-Type': 'application/json'
            },
            "body": json.dumps({
                "clientSecret": payment_intent.client_secret,
                "orderId": order_id,
                "clientId": client_id,
                "jobId": job_id
            })
        }
    except Exception as e:
        logger.error("Error processing checkout: %s", str(e))
        return {
            "statusCode": 400,
            "headers": {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With,Origin,Accept',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
                'Access-Control-Max-Age': '86400',
                'Content-Type': 'application/json'
            },
            "body": json.dumps({"error": str(e)})
        } 