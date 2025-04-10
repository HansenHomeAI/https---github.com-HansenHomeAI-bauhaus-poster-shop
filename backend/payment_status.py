import os
import json
import boto3
import logging
from boto3.dynamodb.conditions import Key

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource("dynamodb")
orders_table_name = os.environ.get("ORDERS_TABLE", "OrdersTable")
table = dynamodb.Table(orders_table_name)

def handler(event, context):
    """
    Checks for payment status updates for a specific client
    This allows the frontend to poll for confirmation from Stripe webhooks
    """
    logger.info(f"Received payment status check: {event}")
    
    # Handle preflight OPTIONS request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        logger.info("Handling OPTIONS preflight request")
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS,HEAD,PATCH',
                'Access-Control-Max-Age': '86400',  # 24 hours
                'Content-Type': 'application/json'
            },
            'body': '{}'
        }
    
    # Extract query parameters
    query_params = event.get('queryStringParameters', {})
    if not query_params:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': json.dumps({'error': 'Missing query parameters'})
        }
    
    client_id = query_params.get('clientId')
    order_id = query_params.get('orderId')
    
    if not client_id:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': json.dumps({'error': 'Missing clientId parameter'})
        }
    
    # If we have an order_id, check that specific order
    if order_id:
        try:
            response = table.get_item(Key={'order_id': order_id})
            order = response.get('Item')
            
            if not order:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,GET'
                    },
                    'body': json.dumps({'error': f'Order {order_id} not found'})
                }
            
            # Check if payment is complete
            status = order.get('status', '')
            if status == 'PAYMENT_COMPLETE' or status == 'PROCESSING':
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,GET'
                    },
                    'body': json.dumps({
                        'success': True,
                        'status': status,
                        'order_id': order_id,
                        'message': 'Payment confirmed'
                    })
                }
            else:
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,GET'
                    },
                    'body': json.dumps({
                        'success': False,
                        'status': status,
                        'order_id': order_id,
                        'message': 'Payment not yet confirmed'
                    })
                }
        except Exception as e:
            logger.error(f"Error checking order status: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,GET'
                },
                'body': json.dumps({'error': f'Error checking order: {str(e)}'})
            }
    
    # Check for status updates for this client
    try:
        # Query for status updates
        # In a real implementation, you might want to use a secondary index
        # Currently just scanning the table as a simple solution
        response = table.scan(
            FilterExpression="client_id = :cid",
            ExpressionAttributeValues={
                ":cid": client_id
            }
        )
        
        items = response.get('Items', [])
        
        # Check if we have any status updates for this client
        payment_complete_items = [item for item in items if item.get('status') in ['PAYMENT_COMPLETE', 'PROCESSING']]
        
        if payment_complete_items:
            # Sort by timestamp to get the most recent
            sorted_items = sorted(payment_complete_items, key=lambda x: x.get('timestamp', 0), reverse=True)
            most_recent = sorted_items[0]
            
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,GET'
                },
                'body': json.dumps({
                    'success': True,
                    'status': most_recent.get('status'),
                    'order_id': most_recent.get('order_id'),
                    'timestamp': most_recent.get('timestamp'),
                    'message': 'Payment confirmed'
                })
            }
        else:
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,GET'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'No payment confirmation found'
                })
            }
    except Exception as e:
        logger.error(f"Error checking status updates: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,GET'
            },
            'body': json.dumps({'error': f'Error checking status: {str(e)}'})
        }

def get_payment_status(event, context):
    try:
        # Extract order ID from the event
        order_id = event['pathParameters']['order_id']
        
        # Get the orders table name from environment variable
        table_name = os.environ['ORDERS_TABLE_NAME']
        
        # Create DynamoDB resource and get reference to the table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        
        # Get the order from the table
        response = table.get_item(
            Key={
                'order_id': order_id
            }
        )
        
        # Check if the order exists
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': 'https://hansenhomeai.github.io',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'GET,OPTIONS'
                },
                'body': json.dumps({
                    'status': 'error',
                    'message': 'Order not found'
                })
            }
        
        # Get the order status
        order = response['Item']
        status = order.get('status', 'UNKNOWN')
        
        # Return the order status
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://hansenhomeai.github.io',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'order_id': order_id,
                'status': status
            })
        }
    except Exception as e:
        logger.error(f"Error getting payment status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://hansenhomeai.github.io',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'GET,OPTIONS'
            },
            'body': json.dumps({
                'status': 'error',
                'message': 'Internal server error'
            })
        } 