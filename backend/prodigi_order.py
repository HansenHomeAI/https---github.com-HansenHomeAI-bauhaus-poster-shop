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
logger.info(f"Using orders table: {orders_table_name}")

# Log available environment variables to help debug (masking sensitive values)
env_vars = {k: v[:4] + '****' if k.lower().find('key') >= 0 else v 
          for k, v in os.environ.items()}
logger.info(f"Environment variables: {json.dumps(env_vars, default=str)}")

try:
    # Test if the table exists
    table = dynamodb.Table(orders_table_name)
    table_details = table.meta.client.describe_table(TableName=orders_table_name)
    logger.info(f"DynamoDB table found: {orders_table_name}, ARN: {table_details['Table']['TableArn']}")
except Exception as e:
    logger.error(f"Failed to connect to DynamoDB table: {str(e)}")
    logger.error(f"Will try to continue anyway with table name: {orders_table_name}")
    table = dynamodb.Table(orders_table_name)

def handler(event, context):
    """
    Creates a print order with Prodigi after payment is confirmed
    """
    logger.info(f"Received Prodigi order request: {json.dumps(event, default=str)}")
    logger.info(f"Using orders table: {orders_table_name}")
    
    # Extract order details from the event
    order_id = event.get("order_id")
    payment_intent = event.get("payment_intent", {})
    
    if not order_id:
        logger.error("No order_id provided")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing order_id"})
        }
    
    # Get customer email from payment intent
    customer_email = payment_intent.get("receipt_email")
    if not customer_email:
        logger.error(f"No customer email found in payment intent for order {order_id}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing customer email"})
        }
    
    # Get the order from DynamoDB to get item details
    try:
        logger.info(f"Attempting to retrieve order {order_id} from DynamoDB table {orders_table_name}")
        response = table.get_item(Key={"order_id": order_id})
        order = response.get("Item")
        
        if not order:
            logger.error(f"Order {order_id} not found in database")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": f"Order {order_id} not found"})
            }
            
        logger.info(f"Retrieved order from DynamoDB: {json.dumps(order, default=str)}")
            
        # Extract order items
        items = order.get("items", [])
        if isinstance(items, str):
            try:
                items = json.loads(items)
                logger.info(f"Parsed items from JSON string: {json.dumps(items, default=str)}")
            except Exception as e:
                logger.error(f"Error parsing items JSON: {str(e)}")
                items = []
                
        if not items:
            logger.error(f"No items found in order {order_id}")
            # For orders without items, create a default item
            # This is a fallback for orders created before the fix
            items = [{
                "id": "default",
                "name": "Bauhaus Poster",
                "price": order.get("amount_paid", 0) / 100 if order.get("amount_paid") else 50,
                "quantity": 1
            }]
            logger.info(f"Created default item for order {order_id}: {json.dumps(items, default=str)}")
        
        # Build the Prodigi order payload
        prodigi_items = []
        for item in items:
            prodigi_item = {
                "sku": "GLOBAL-POSTER-40x30",  # This should match a valid Prodigi SKU
                "quantity": item.get("quantity", 1),
                "sizing": "cover",
                "attributes": {
                    "color": "white"
                }
            }
            
            # Add the image URL if it exists in the item
            if "imageUrl" in item:
                prodigi_item["assets"] = [{
                    "printArea": "default",
                    "url": item["imageUrl"]
                }]
            else:
                # Fallback image URL for older orders
                poster_id = item.get("id", "default")
                prodigi_item["assets"] = [{
                    "printArea": "default",
                    "url": f"https://bauhaus-poster-gallery.s3.us-west-2.amazonaws.com/poster-{poster_id}.jpg"
                }]
            
            prodigi_items.append(prodigi_item)
            
        prodigi_payload = {
            "shippingMethod": "GLOBAL_ECONOMY",
            "recipient": {
                "name": customer_email.split('@')[0],  # Use part of email as name
                "email": customer_email,
                "address": {
                    "line1": "123 Placeholder St",
                    "line2": "",
                    "postalOrZipCode": "00000",
                    "countryCode": "US",
                    "townOrCity": "Any City",
                    "stateOrCounty": "CA"
                }
            },
            "items": prodigi_items,
            "idempotencyKey": order_id
        }
        
        # Get Prodigi API key
        prodigi_api_key = os.environ.get("PRODIGI_API_KEY")
        if not prodigi_api_key:
            logger.error("No Prodigi API key configured")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Missing Prodigi API configuration"})
            }
        
        logger.info(f"Sending order to Prodigi with API key: {prodigi_api_key[:4]}*****")
        
        # Validate the API key format
        if prodigi_api_key.startswith("test") or prodigi_api_key.startswith("prod"):
            logger.info("API key format appears valid")
        else:
            logger.warning(f"API key format may be invalid - does not start with 'test' or 'prod'")
        
        # Send order to Prodigi
        headers = {
            "X-API-Key": prodigi_api_key,
            "Content-Type": "application/json"
        }
        prodigi_url = "https://api.prodigi.com/v4.0/orders"
        
        logger.info(f"Prodigi payload: {json.dumps(prodigi_payload, default=str)}")
        
        response = requests.post(prodigi_url, headers=headers, json=prodigi_payload)
        
        logger.info(f"Prodigi API response status: {response.status_code}")
        logger.info(f"Prodigi API response body: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            order_response = response.json()
            logger.info(f"Prodigi order created: {json.dumps(order_response, default=str)}")
            
            # Update the order in DynamoDB with Prodigi order ID
            prodigi_order_id = order_response.get("id")
            
            if prodigi_order_id:
                update_response = table.update_item(
                    Key={"order_id": order_id},
                    UpdateExpression="SET prodigi_order_id = :poi, #status_field = :status, updated_at = :time",
                    ExpressionAttributeValues={
                        ":poi": prodigi_order_id,
                        ":status": "PROCESSING",
                        ":time": int(time.time())
                    },
                    ExpressionAttributeNames={
                        "#status_field": "status"
                    },
                    ReturnValues="ALL_NEW"
                )
                
                logger.info(f"Updated order {order_id} with Prodigi order ID {prodigi_order_id}")
                logger.info(f"Updated order record: {json.dumps(update_response.get('Attributes', {}), default=str)}")
            
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "Prodigi order created successfully",
                    "prodigi_order_id": prodigi_order_id,
                    "prodigi_response": order_response
                })
            }
        else:
            error_message = f"Failed to create Prodigi order: {response.text}"
            logger.error(error_message)
            
            # Check for authentication issues
            if response.status_code == 401:
                logger.error("Authentication failed with Prodigi API. Please check your API key.")
                
                # Check the environment variable value directly
                raw_api_key = os.environ.get("PRODIGI_API_KEY", "")
                logger.info(f"Raw API key length: {len(raw_api_key)}, first/last chars: {raw_api_key[:2]}...{raw_api_key[-2:] if len(raw_api_key) > 2 else ''}")
            
            # Update the order with error status
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET #status_field = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "PRODIGI_ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
                },
                ExpressionAttributeNames={
                    "#status_field": "status"
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
        error_message = f"Error creating Prodigi order: {str(e)}"
        logger.error(error_message)
        logger.error(traceback.format_exc())
        
        # Try to update the order with error status
        try:
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET #status_field = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
                },
                ExpressionAttributeNames={
                    "#status_field": "status"
                }
            )
        except Exception as update_error:
            logger.error(f"Failed to update order status: {str(update_error)}")
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        } 