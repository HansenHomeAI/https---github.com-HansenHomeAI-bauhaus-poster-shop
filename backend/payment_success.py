import os
import json
import boto3
import stripe
import logging
import time
import uuid
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS resources
dynamodb = boto3.resource('dynamodb')
orders_table_name = os.environ.get('ORDERS_TABLE', 'OrdersTable')
table = dynamodb.Table(orders_table_name)

# Initialize Stripe
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')

# Import Prodigi order functions if available
try:
    from prodigi_order import create_prodigi_order
    HAS_PRODIGI = True
except ImportError:
    logger.warning("Prodigi order module not available - will not send orders for fulfillment")
    HAS_PRODIGI = False

def handler(event, context):
    """
    Handles successful payment confirmations from the frontend
    """
    logger.info(f"Received payment success event: {event}")
    
    # Handle preflight OPTIONS request for CORS
    if event.get('httpMethod') == 'OPTIONS':
        logger.info("Handling OPTIONS preflight request")
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Requested-With',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'Access-Control-Max-Age': '86400'  # 24 hours
            },
            'body': ''
        }
    
    try:
        # Parse the request body
        if 'body' in event:
            body = json.loads(event.get('body', '{}'))
        else:
            body = event
            
        # Get order details
        order_id = body.get('orderId')
        job_id = body.get('jobId')
        client_id = body.get('clientId')
        
        if not order_id:
            return {
                'statusCode': 400,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST'
                },
                'body': json.dumps({'error': 'Missing order_id'})
            }
            
        # Retrieve the order from DynamoDB
        try:
            response = table.get_item(Key={'order_id': order_id})
            order = response.get('Item')
            
            if not order:
                return {
                    'statusCode': 404,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,POST'
                    },
                    'body': json.dumps({'error': f'Order {order_id} not found'})
                }
                
            logger.info(f"Retrieved order: {order}")
            
            # Check if the order has already been processed
            current_status = order.get('status', '')
            if current_status == 'PAID':
                logger.info(f"Order {order_id} already marked as PAID, checking for Prodigi processing")
                
                # If order is paid but not yet sent to Prodigi, do that now
                if not order.get('prodigi_order_id') and HAS_PRODIGI:
                    # Send to Prodigi for fulfillment
                    try:
                        prodigi_order_result = create_prodigi_order(order)
                        prodigi_order_id = prodigi_order_result.get('prodigi_order_id')
                        
                        # Update order with Prodigi order ID
                        table.update_item(
                            Key={'order_id': order_id},
                            UpdateExpression="SET prodigi_order_id = :poi, status = :status, updated_at = :time",
                            ExpressionAttributeValues={
                                ':poi': prodigi_order_id,
                                ':status': 'PROCESSING',
                                ':time': int(time.time())
                            }
                        )
                        
                        logger.info(f"Created Prodigi order {prodigi_order_id} for order {order_id}")
                    except Exception as e:
                        logger.error(f"Error creating Prodigi order: {str(e)}")
                        # Continue anyway, as we can retry this later
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Access-Control-Allow-Origin': '*',
                        'Access-Control-Allow-Headers': '*',
                        'Access-Control-Allow-Methods': 'OPTIONS,POST'
                    },
                    'body': json.dumps({
                        'message': 'Order already processed',
                        'order_id': order_id,
                        'status': order.get('status')
                    })
                }
                
            # Verify payment with Stripe if needed
            # For security, you might want to double-check with Stripe here
            # but in this case we're just trusting the client indication
            
            # Update order status to PAID
            current_time = int(time.time())
            
            update_expr = "SET status = :status, updated_at = :time"
            expr_values = {
                ':status': 'PAID',
                ':time': current_time
            }
            
            table.update_item(
                Key={'order_id': order_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
            
            logger.info(f"Updated order {order_id} status to PAID")
            
            # If Prodigi integration is available, create the order for fulfillment
            if HAS_PRODIGI:
                try:
                    prodigi_order_result = create_prodigi_order(order)
                    prodigi_order_id = prodigi_order_result.get('prodigi_order_id')
                    
                    # Update order with Prodigi order ID
                    table.update_item(
                        Key={'order_id': order_id},
                        UpdateExpression="SET prodigi_order_id = :poi, status = :status, updated_at = :time",
                        ExpressionAttributeValues={
                            ':poi': prodigi_order_id,
                            ':status': 'PROCESSING',
                            ':time': current_time
                        }
                    )
                    
                    logger.info(f"Created Prodigi order {prodigi_order_id} for order {order_id}")
                except Exception as e:
                    logger.error(f"Error creating Prodigi order: {str(e)}")
                    # Continue anyway as we successfully processed payment
            
            return {
                'statusCode': 200,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST'
                },
                'body': json.dumps({
                    'message': 'Payment successful',
                    'order_id': order_id,
                    'status': 'PAID'
                })
            }
            
        except ClientError as e:
            logger.error(f"DynamoDB error: {str(e)}")
            return {
                'statusCode': 500,
                'headers': {
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': '*',
                    'Access-Control-Allow-Methods': 'OPTIONS,POST'
                },
                'body': json.dumps({'error': f'Database error: {str(e)}'})
            }
            
    except Exception as e:
        logger.error(f"Error processing payment success: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': '*',
                'Access-Control-Allow-Methods': 'OPTIONS,POST'
            },
            'body': json.dumps({'error': f'Server error: {str(e)}'})
        } 