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
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Order has no items"})
            }
        
        # Build the Prodigi order payload
        prodigi_items = []
        for item in items:
            prodigi_items.append({
                "sku": "GLOBAL-POSTER-40x30",  # This should match a valid Prodigi SKU
                "quantity": item.get("quantity", 1),
                "sizing": "cover",
                "attributes": {
                    "color": "white"
                }
            })
            
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
        
        # Send order to Prodigi
        headers = {
            "X-API-Key": prodigi_api_key,
            "Content-Type": "application/json"
        }
        prodigi_url = "https://api.prodigi.com/v4.0/orders"
        
        logger.info(f"Sending order to Prodigi with API key: {prodigi_api_key[:4]}*****")
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
                    UpdateExpression="SET prodigi_order_id = :poi, status = :status, updated_at = :time",
                    ExpressionAttributeValues={
                        ":poi": prodigi_order_id,
                        ":status": "PROCESSING",
                        ":time": int(time.time())
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
            
            # Update the order with error status
            table.update_item(
                Key={"order_id": order_id},
                UpdateExpression="SET status = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "PRODIGI_ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
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
                UpdateExpression="SET status = :status, error_message = :error, updated_at = :time",
                ExpressionAttributeValues={
                    ":status": "ERROR",
                    ":error": error_message,
                    ":time": int(time.time())
                }
            )
        except Exception as update_error:
            logger.error(f"Failed to update order status: {str(update_error)}")
        
        return {
            "statusCode": 500,
            "body": json.dumps({"error": error_message})
        } 