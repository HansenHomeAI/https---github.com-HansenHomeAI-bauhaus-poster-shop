import os
import json
import boto3
import logging

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ORDERS_TABLE"))

def handler(event, context):
    logger.info(f"Order status request: {event}")
    
    # Add CORS headers
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,OPTIONS"
    }
    
    # Handle OPTIONS request (preflight)
    if event.get("httpMethod") == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"message": "CORS preflight successful"})
        }
    
    params = event.get("queryStringParameters", {}) or {}
    # Check both order_id and orderId (frontend might use camelCase)
    order_id = params.get("order_id") or params.get("orderId")

    logger.info(f"Looking up order: {order_id}")

    if not order_id:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "order_id query parameter is required"})
        }
    
    try:
        response = table.get_item(Key={"order_id": order_id})
        order = response.get("Item")
        
        if not order:
            return {
                "statusCode": 404,
                "headers": headers,
                "body": json.dumps({"error": "Order not found"})
            }
        
        # Clean up the response to remove any sensitive information
        status_response = {
            "order_id": order.get("order_id"),
            "status": order.get("status"),
            "payment_status": order.get("payment_status"),
            "updated_at": order.get("updated_at"),
            "prodigi_order_id": order.get("prodigi_order_id")
        }
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(status_response)
        }
    except Exception as e:
        logger.error(f"Error retrieving order status: {str(e)}")
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": f"Error retrieving order: {str(e)}"})
        } 