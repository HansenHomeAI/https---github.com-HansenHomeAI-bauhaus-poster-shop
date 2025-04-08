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
import os

class BackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
        create_checkout_session = _lambda.Function(
            self, "CreateCheckoutSession",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("backend/functions"),
            handler="create_checkout_session.handler",
            environment={
                "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
                "SUCCESS_URL": os.getenv("SUCCESS_URL"),
                "CANCEL_URL": os.getenv("CANCEL_URL"),
                "ORDERS_TABLE": orders_table.table_name
            }
        )

        stripe_webhook = _lambda.Function(
            self, "StripeWebhook",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("backend/functions"),
            handler="stripe_webhook.handler",
            environment={
                "STRIPE_SECRET_KEY": os.getenv("STRIPE_SECRET_KEY"),
                "STRIPE_WEBHOOK_SECRET": os.getenv("STRIPE_WEBHOOK_SECRET"),
                "PRODIGI_API_KEY": os.getenv("PRODIGI_API_KEY"),
                "EMAIL_SENDER": os.getenv("EMAIL_SENDER"),
                "ORDERS_TABLE": orders_table.table_name
            }
        )

        get_order = _lambda.Function(
            self, "GetOrder",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset("backend/functions"),
            handler="get_order.handler",
            environment={
                "ORDERS_TABLE": orders_table.table_name
            }
        )

        # Grant permissions
        orders_table.grant_write_data(create_checkout_session)
        orders_table.grant_write_data(stripe_webhook)
        orders_table.grant_read_data(get_order)

        # Create API Gateway
        api = apigw.RestApi(
            self, "BauhausPosterShopAPI",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS
            )
        )

        # Add resources and methods
        checkout = api.root.add_resource("checkout")
        checkout.add_method(
            "POST",
            apigw.LambdaIntegration(create_checkout_session)
        )

        webhook = api.root.add_resource("webhook")
        webhook.add_method(
            "POST",
            apigw.LambdaIntegration(stripe_webhook)
        )

        orders = api.root.add_resource("orders")
        order = orders.add_resource("{order_id}")
        order.add_method(
            "GET",
            apigw.LambdaIntegration(get_order)
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
                "EMAIL_SENDER": os.getenv("EMAIL_SENDER")
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

        # Add order status endpoint
        order_status = api.root.add_resource("order-status")
        order_status.add_method(
            "GET",
            apigw.LambdaIntegration(order_status_lambda)
        )

        # Grant permissions
        orders_table.grant_write_data(prodigi_webhook_lambda)
        orders_table.grant_read_data(order_status_lambda) 