import os
import json
import stripe
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Stripe with your secret key
stripe_secret_key = os.environ.get("STRIPE_SECRET_KEY", "DEFAULT_NOT_SET")
logger.info(f"Using Stripe secret key: {stripe_secret_key[:8]}...")

stripe.api_key = stripe_secret_key
stripe.api_version = "2023-10-16"

def handler(event, context):
    """
    Simple Stripe API test endpoint
    """
    logger.info("Received test event")
    
    response_headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Content-Type': 'application/json'
    }
    
    try:
        # Try to retrieve Stripe account info
        account = stripe.Account.retrieve()
        
        return {
            "statusCode": 200,
            "headers": response_headers,
            "body": json.dumps({
                "success": True,
                "account_id": account.id,
                "account_name": account.settings.dashboard.display_name if hasattr(account, 'settings') else "Unknown",
                "api_version": stripe.api_version,
                "test_mode": account.charges_enabled and not account.details_submitted
            })
        }
    except Exception as e:
        logger.error(f"Error testing Stripe API: {str(e)}")
        return {
            "statusCode": 400,
            "headers": response_headers,
            "body": json.dumps({
                "success": False,
                "error": str(e),
                "api_key_first_chars": stripe_secret_key[:4] + "..." if stripe_secret_key else "Not set"
            })
        } 