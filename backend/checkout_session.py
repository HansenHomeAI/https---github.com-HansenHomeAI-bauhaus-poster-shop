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
        return create_cors_response(200, '')

    try:
        # Log the incoming request details
        logger.info("Request headers: %s", event.get('headers', {}))
        logger.info("Request body: %s", event.get('body', '{}'))

        body = json.loads(event.get("body", "{}"))
        items = body.get("items", [])
        customer_email = body.get("customerEmail")  # Updated to match frontend

        if not items:
            return create_cors_response(400, {"error": "No items provided in request"})

        # Build Stripe line items array
        line_items = []
        for item in items:
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": item.get("name"),
                    },
                    "unit_amount": int(float(item.get("price")) * 100),
                },
                "quantity": item.get("quantity"),
            })

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            customer_email=customer_email,
            success_url=os.environ.get("SUCCESS_URL", "https://hansenhomeai.github.io/success") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.environ.get("CANCEL_URL", "https://hansenhomeai.github.io/cancel"),
            metadata={
                "order_id": str(uuid.uuid4())
            }
        )
        
        logger.info("Successfully created Stripe session: %s", session.id)
        return create_cors_response(200, {"sessionId": session.id})

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body: %s", str(e))
        return create_cors_response(400, {"error": "Invalid JSON in request body"})
    except stripe.error.StripeError as e:
        logger.error("Stripe error: %s", str(e))
        return create_cors_response(400, {"error": str(e)})
    except Exception as e:
        logger.error("Error processing checkout: %s", str(e))
        return create_cors_response(500, {"error": str(e)}) 