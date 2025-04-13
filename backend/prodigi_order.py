import os
import json
import requests
import logging
import boto3
import time
import traceback

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource('dynamodb')
orders_table_name = os.environ.get('ORDERS_TABLE', 'OrdersTable')
table = dynamodb.Table(orders_table_name)

def handler(event, context):
    """
    Creates a print order with Prodigi after payment is confirmed
    """
    logger.info(f"Received Prodigi order request: {json.dumps(event, default=str)}")
    logger.info(f"Using orders table: {orders_table_name}")
    
    # Extract order details from the event
    order_id = event.get("order_id")
    order_data = event.get("order_data", {})
    payment_intent = event.get("payment_intent", {})
    
    if not order_id:
        logger.error("No order_id provided")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing order_id"})
        }

    # If no order data provided, try to get it from DynamoDB
    if not order_data:
        logger.info(f"No order data in event, retrieving from DynamoDB")
        try:
            response = table.get_item(Key={"order_id": order_id})
            order_data = response.get("Item", {})
            
            if not order_data:
                logger.error(f"Order {order_id} not found in database")
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": f"Order {order_id} not found"})
                }
            
            logger.info(f"Retrieved order from DynamoDB: {json.dumps(order_data, default=str)}")
        except Exception as e:
            logger.error(f"Error retrieving order: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Error retrieving order: {str(e)}"})
            }
    
    # Parse items from order data
    items_json = order_data.get("items", "[]")
    if isinstance(items_json, str):
        try:
            items = json.loads(items_json)
            logger.info(f"Parsed items from JSON string, found {len(items)} items")
        except Exception as e:
            logger.error(f"Error parsing items JSON: {str(e)}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Invalid items data: {str(e)}"})
            }
    else:
        items = items_json
    
    if not items:
        logger.error(f"No items found in order {order_id}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Order has no items"})
        }
    
    # Get customer email
    customer_email = order_data.get("customer_email") or payment_intent.get("receipt_email")
    if not customer_email:
        logger.error(f"No customer email found for order {order_id}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing customer email"})
        }
    
    logger.info(f"Processing order {order_id} with {len(items)} items for {customer_email}")
    
    # Get customer shipping details
    shipping_details = order_data.get("shipping_details", {})
    if not shipping_details:
        logger.error(f"No shipping details found for order {order_id}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing shipping details"})
        }
        
    logger.info(f"Shipping details: {json.dumps(shipping_details, default=str)}")
    
    # Get Prodigi Sandbox API key - ONLY use sandbox for testing
    prodigi_api_key = os.environ.get("PRODIGI_SANDBOX_API_KEY")
    logger.info(f"Available Prodigi env vars: {[k for k in os.environ.keys() if 'PRODIGI' in k]}")
    
    if not prodigi_api_key:
        logger.error("PRODIGI_SANDBOX_API_KEY not set in environment variables")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Missing Prodigi Sandbox API configuration"})
        }
    
    # Show a masked version of the API key for debugging
    masked_key = prodigi_api_key[:4] + '*' * 5
    logger.info(f"Using Prodigi API key: {masked_key}")
    
    # Build the Prodigi order payload
    prodigi_items = []
    for item in items:
        # Map to valid Prodigi SKUs
        sku = "GLOBAL-POSTER-16x12"  # Default SKU for posters
        
        # Extract image file from item
        image_url = item.get("image", "")
        if not image_url:
            logger.error(f"No image URL found for item: {json.dumps(item, default=str)}")
            continue
            
        # Transform relative path to absolute URL if needed
        if image_url.startswith("assets/"):
            image_url = f"https://hansenhomeai.github.io/{image_url}"
            
        prodigi_items.append({
            "sku": sku,
            "copies": item.get("quantity", 1),
            "sizing": "fillPrintArea",  # Valid values: fillPrintArea, fitPrintArea
            "assets": [
                {
                    "printArea": "default",
                    "url": image_url
                }
            ],
            "attributes": {
                "color": "white"
            }
        })
    
    # Get customer name from shipping details
    first_name = shipping_details.get("firstName", "").strip()
    last_name = shipping_details.get("lastName", "").strip()
    customer_name = f"{first_name} {last_name}".strip()
    
    if not customer_name:
        # Fallback to email if no name provided
        customer_name = customer_email.split('@')[0]
        if not customer_name or len(customer_name) < 2:
            customer_name = "Customer"
    
    # Map shipping method to valid Prodigi values
    shipping_method = shipping_details.get("shippingMethod", "BUDGET")
    prodigi_shipping_method = {
        "BUDGET": "BUDGET",
        "STANDARD": "STANDARD",
        "EXPRESS": "EXPRESS",
        "PRIORITY": "PRIORITY"
    }.get(shipping_method, "BUDGET")
    
    prodigi_payload = {
        "shippingMethod": prodigi_shipping_method,
        "recipient": {
            "name": customer_name,
            "email": customer_email,
            "phoneNumber": shipping_details.get("phone", ""),
            "address": {
                "line1": shipping_details.get("address1", ""),
                "line2": shipping_details.get("address2", "Apt 1"),  # Prodigi requires line2
                "postalOrZipCode": shipping_details.get("postalCode", ""),
                "countryCode": shipping_details.get("country", "US"),
                "townOrCity": shipping_details.get("city", ""),
                "stateOrCounty": shipping_details.get("state", "")
            }
        },
        "items": prodigi_items,
        "idempotencyKey": order_id
    }
    
    # Send order to Prodigi
    headers = {
        "X-API-Key": prodigi_api_key,
        "Content-Type": "application/json"
    }
    
    # Determine API endpoint based on environment
    # When using PRODIGI_SANDBOX_API_KEY, always use sandbox endpoint
    prodigi_url = "https://api.sandbox.prodigi.com/v4.0/orders"
    logger.info("Using Prodigi SANDBOX API endpoint")
    
    logger.info(f"Sending order to Prodigi")
    logger.info(f"Prodigi payload: {json.dumps(prodigi_payload, default=str)}")
    
    try:
        response = requests.post(prodigi_url, headers=headers, json=prodigi_payload)
        
        logger.info(f"Prodigi API response status: {response.status_code}")
        logger.info(f"Prodigi API response body: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            # Success - update the order with the Prodigi ID
            order_response = response.json()
            prodigi_order_id = order_response.get("id")
            
            if prodigi_order_id:
                update_response = table.update_item(
                    Key={"order_id": order_id},
                    UpdateExpression="SET prodigi_order_id = :poi, #status_attr = :status, updated_at = :time",
                    ExpressionAttributeValues={
                        ":poi": prodigi_order_id,
                        ":status": "PROCESSING",
                        ":time": int(time.time())
                    },
                    ExpressionAttributeNames={
                        "#status_attr": "status"
                    },
                    ReturnValues="ALL_NEW"
                )
                
                logger.info(f"Updated order with Prodigi order ID: {prodigi_order_id}")
                
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Order submitted to Prodigi successfully",
                    "prodigi_order_id": prodigi_order_id
                })
            }
        else:
            # Error from Prodigi API
            error_message = f"Prodigi API error: {response.text}"
            logger.error(error_message)
            
            if response.status_code == 401:
                logger.error("Authentication failed. Check your API key.")
            
            # Update the order with the error
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET #status_attr = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
                },
                ExpressionAttributeNames={
                    "#status_attr": "status"
                }
            )
            
            return {
                "statusCode": response.status_code,
                "body": json.dumps({
                    "error": "Failed to create Prodigi order",
                    "details": response.text
                })
            }
    
    except Exception as e:
        # Handle any other errors
        error_message = f"Error processing order: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        
        # Update the order with the error
        try:
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET #status_attr = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
                },
                ExpressionAttributeNames={
                    "#status_attr": "status"
                }
            )
        except Exception as update_error:
            logger.error(f"Failed to update order status: {str(update_error)}")
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        } 