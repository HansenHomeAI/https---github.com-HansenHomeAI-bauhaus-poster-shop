import os
import json
import boto3

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("ORDERS_TABLE"))

def handler(event, context):
    params = event.get("queryStringParameters", {})
    order_id = params.get("order_id")

    if not order_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "order_id query parameter is required"})
        }
    
    response = table.get_item(Key={"order_id": order_id})
    order = response.get("Item")
    
    if not order:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Order not found"})
        }
    
    return {
        "statusCode": 200,
        "body": json.dumps(order)
    } 