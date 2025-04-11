import os
import json
import boto3
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource('dynamodb')
orders_table_name = os.environ.get('ORDERS_TABLE')
logger.info(f"Using orders table from environment: {orders_table_name}")
table = dynamodb.Table(orders_table_name)

def handler(event, context):
    """
    Gets the status of an order
    """
    logger.info(f"Received order status check event: {json.dumps(event)}")
    
    # Handle OPTIONS request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'Content-Type': 'application/json'
            },
            'body': '{}'
        }
        
    # Get order ID from query parameters
    query_params = event.get('queryStringParameters', {})
    order_id = query_params.get('orderId')
    
    if not order_id:
        logger.error("No order ID provided")
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': 'Missing orderId parameter'
            })
        }
        
    try:
        logger.info(f"Retrieving order {order_id} from table {orders_table_name}")
        response = table.get_item(Key={'order_id': order_id})
        order = response.get('Item')
        
        if not order:
            logger.error(f"Order {order_id} not found")
            return {
                'statusCode': 404,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Content-Type': 'application/json'
                },
                'body': json.dumps({
                    'error': f'Order {order_id} not found'
                })
            }
            
        logger.info(f"Found order: {json.dumps(order, default=str)}")
        
        # Clean up order data for response
        if 'items' in order and isinstance(order['items'], str):
            try:
                order['items'] = json.loads(order['items'])
            except:
                pass
                
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'order': order,
                'message': f"Order status: {order.get('status', 'UNKNOWN')}"
            })
        }
        
    except Exception as e:
        logger.error(f"Error retrieving order status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Content-Type': 'application/json'
            },
            'body': json.dumps({
                'error': f'Error retrieving order: {str(e)}'
            })
        } 