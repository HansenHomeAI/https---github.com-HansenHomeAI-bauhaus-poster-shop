from aws_cdk import (
    App,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

class BackendStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # DynamoDB Table for Orders
        orders_table = dynamodb.Table(
            self, "OrdersTable",
            partition_key=dynamodb.Attribute(name="order_id", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY  # In production, consider using RETAIN.
        )

        # Lambda: Create Checkout Session
        checkout_lambda = lambda_.Function(
            self, "CreateCheckoutSessionLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="checkout_session.handler",
            code=lambda_.Code.from_asset("backend"),
            environment={
                "STRIPE_SECRET_KEY": "YOUR_STRIPE_SECRET_KEY",
                "SUCCESS_URL": "https://yourdomain.com/success",
                "CANCEL_URL": "https://yourdomain.com/cancel"
            }
        )

        # Lambda: Stripe Webhook
        stripe_webhook_lambda = lambda_.Function(
            self, "StripeWebhookLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="stripe_webhook.handler",
            code=lambda_.Code.from_asset("backend"),
            environment={
                "STRIPE_SECRET_KEY": "YOUR_STRIPE_SECRET_KEY",
                "STRIPE_WEBHOOK_SECRET": "YOUR_STRIPE_WEBHOOK_SECRET",
                "ORDERS_TABLE": orders_table.table_name,
                "PRODIGI_ORDER_FUNCTION_NAME": "ProdigiOrderLambda"  # Will be set later
            }
        )
        orders_table.grant_write_data(stripe_webhook_lambda)

        # Lambda: Prodigi Order Creation
        prodigi_order_lambda = lambda_.Function(
            self, "ProdigiOrderLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="prodigi_order.handler",
            code=lambda_.Code.from_asset("backend"),
            environment={
                "PRODIGI_API_KEY": "YOUR_PRODIGI_API_KEY",
                "ORDERS_TABLE": orders_table.table_name
            }
        )
        orders_table.grant_write_data(prodigi_order_lambda)

        # Lambda: Prodigi Webhook (Shipping Updates)
        prodigi_webhook_lambda = lambda_.Function(
            self, "ProdigiWebhookLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="prodigi_webhook.handler",
            code=lambda_.Code.from_asset("backend"),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
                "EMAIL_SENDER": "noreply@yourdomain.com"
            }
        )
        orders_table.grant_write_data(prodigi_webhook_lambda)

        # Lambda: Order Status (GET)
        order_status_lambda = lambda_.Function(
            self, "OrderStatusLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="order_status.handler",
            code=lambda_.Code.from_asset("backend"),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
            }
        )
        orders_table.grant_read_data(order_status_lambda)

        # API Gateway REST API
        api = apigateway.RestApi(self, "BackendApi",
            rest_api_name="Backend Service",
            description="Handles Stripe checkout sessions, webhooks, and Prodigi order processing."
        )

        # /create-checkout-session endpoint
        create_checkout_resource = api.root.add_resource("create-checkout-session")
        create_checkout_resource.add_method("POST", apigateway.LambdaIntegration(checkout_lambda))

        # /stripe-webhook endpoint
        stripe_webhook_resource = api.root.add_resource("stripe-webhook")
        stripe_webhook_resource.add_method("POST", apigateway.LambdaIntegration(stripe_webhook_lambda))

        # /prodigi-webhook endpoint
        prodigi_webhook_resource = api.root.add_resource("prodigi-webhook")
        prodigi_webhook_resource.add_method("POST", apigateway.LambdaIntegration(prodigi_webhook_lambda))

        # /order-status endpoint
        order_status_resource = api.root.add_resource("order-status")
        order_status_resource.add_method("GET", apigateway.LambdaIntegration(order_status_lambda)) 