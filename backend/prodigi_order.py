import os
import json
import requests
import logging

def handler(event, context):
    order_id = event.get("order_id")
    stripe_session = event.get("stripe_session")
    customer_email = stripe_session.get("customer_email")

    # Build the Prodigi order payload per Prodigi API docs (https://www.prodigi.com/api-docs)
    prodigi_payload = {
        "recipient": {
            "name": customer_email,  # Replace with actual recipient name if available
            "email": customer_email,
            "address": {
                "line1": "123 Placeholder St",
                "city": "Placeholder City",
                "state": "XX",
                "postalCode": "00000",
                "country": "US"
            }
        },
        "items": [
            {
                "sku": "POSTER-001",
                "quantity": 1,
                "options": {
                    "size": "A2"
                }
            }
        ],
        "reference": order_id
    }

    prodigi_api_key = os.environ.get("PRODIGI_API_KEY")
    headers = {
        "Authorization": f"Basic {prodigi_api_key}",
        "Content-Type": "application/json"
    }
    prodigi_url = "https://api.prodigi.com/v4/orders"  # Refer to Prodigi API documentation
    response = requests.post(prodigi_url, headers=headers, json=prodigi_payload)

    if response.status_code in [200, 201]:
        order_response = response.json()
        logging.info(f"Prodigi order created: {order_response}")
    else:
        logging.error(f"Failed to create Prodigi order: {response.text}")

    return {
        "statusCode": response.status_code,
        "body": response.text
    } 