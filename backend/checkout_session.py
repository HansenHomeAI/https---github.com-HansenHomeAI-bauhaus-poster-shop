import os
import json
import stripe
import uuid

# Initialize Stripe with your secret key
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    items = body.get("items", [])
    customer_email = body.get("customer_email")

    # Build Stripe line items array
    line_items = []
    for item in items:
        line_items.append({
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": item.get("name"),
                    "description": item.get("description"),
                    "images": [item.get("image")],
                },
                "unit_amount": int(float(item.get("price")) * 100),
            },
            "quantity": item.get("quantity"),
        })

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            customer_email=customer_email,
            success_url=os.environ.get("SUCCESS_URL") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=os.environ.get("CANCEL_URL"),
            metadata={
                "order_id": str(uuid.uuid4())
            }
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"sessionId": session.id})
        }
    except Exception as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": str(e)})
        } 