from aws_cdk import (
    App,
    RemovalPolicy,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    Duration
)
from constructs import Construct

class BackendStack(Stack):
    def __init__(
        self, 
        scope: Construct, 
        id: str, 
        stripe_secret_key: str,
        stripe_webhook_secret: str,
        prodigi_api_key: str,
        email_sender: str,
        success_url: str,
        cancel_url: str,
        **kwargs
    ):
        super().__init__(scope, id, **kwargs)

        # Create DynamoDB table for orders
        orders_table = dynamodb.Table(
            self, "OrdersTable",
            partition_key=dynamodb.Attribute(
                name="order_id",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create Lambda functions
        create_checkout_lambda = _lambda.Function(
            self, "CreateCheckoutFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="checkout_session.handler",
            code=_lambda.Code.from_asset(
                "backend",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            timeout=Duration.seconds(30),
            environment={
                "STRIPE_SECRET_KEY": stripe_secret_key,
                "SUCCESS_URL": success_url,
                "CANCEL_URL": cancel_url,
                "ORDERS_TABLE_NAME": orders_table.table_name
            }
        )

        stripe_webhook_lambda = _lambda.Function(
            self, "StripeWebhookFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="stripe_webhook.handler",
            code=_lambda.Code.from_asset(
                "backend",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            timeout=Duration.seconds(30),
            environment={
                "STRIPE_SECRET_KEY": stripe_secret_key,
                "STRIPE_WEBHOOK_SECRET": stripe_webhook_secret,
                "ORDERS_TABLE_NAME": orders_table.table_name
            }
        )

        process_order_lambda = _lambda.Function(
            self, "ProcessOrderFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="process_order.handler",
            code=_lambda.Code.from_asset(
                "backend",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            timeout=Duration.seconds(30),
            environment={
                "PRODIGI_API_KEY": prodigi_api_key,
                "EMAIL_SENDER": email_sender,
                "ORDERS_TABLE_NAME": orders_table.table_name
            }
        )

        # Prodigi Webhook Lambda
        prodigi_webhook_lambda = _lambda.Function(
            self, "ProdigiWebhookLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="prodigi_webhook.handler",
            code=_lambda.Code.from_asset(
                "backend",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
                "EMAIL_SENDER": email_sender
            }
        )

        # Order Status Lambda
        order_status_lambda = _lambda.Function(
            self, "OrderStatusLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="order_status.handler",
            code=_lambda.Code.from_asset(
                "backend",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
            }
        )

        # Create API Gateway with CORS enabled
        api = apigw.RestApi(
            self, "PosterShopApi",
            rest_api_name="Poster Shop API",
            description="API for the Bauhaus Poster Shop",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["*"],
                allow_credentials=False,
                max_age=Duration.days(1)
            )
        )

        # Add checkout endpoint
        checkout = api.root.add_resource("checkout")
        checkout_integration = apigw.LambdaIntegration(
            create_checkout_lambda,
            proxy=True,
            integration_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': "'*'",
                    'method.response.header.Access-Control-Allow-Headers': "'*'",
                    'method.response.header.Access-Control-Allow-Methods': "'OPTIONS,POST'"
                }
            }]
        )
        
        checkout.add_method(
            "POST",
            checkout_integration,
            method_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': True,
                    'method.response.header.Access-Control-Allow-Headers': True,
                    'method.response.header.Access-Control-Allow-Methods': True
                }
            }]
        )

        # Add webhook endpoints
        webhook = api.root.add_resource("webhook")
        webhook.add_method(
            "POST",
            apigw.LambdaIntegration(stripe_webhook_lambda)
        )

        prodigi_webhook = api.root.add_resource("prodigi-webhook")
        prodigi_webhook.add_method(
            "POST",
            apigw.LambdaIntegration(prodigi_webhook_lambda)
        )

        # Add order status endpoint
        order_status = api.root.add_resource("order-status")
        order_status.add_method(
            "GET",
            apigw.LambdaIntegration(order_status_lambda)
        )

        # Grant permissions
        orders_table.grant_write_data(create_checkout_lambda)
        orders_table.grant_read_write_data(stripe_webhook_lambda)
        orders_table.grant_read_write_data(process_order_lambda)
        orders_table.grant_write_data(prodigi_webhook_lambda)
        orders_table.grant_read_data(order_status_lambda) 