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
            handler="create_checkout.handler",
            code=_lambda.Code.from_asset("backend"),
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
            code=_lambda.Code.from_asset("backend"),
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
            code=_lambda.Code.from_asset("backend"),
            timeout=Duration.seconds(30),
            environment={
                "PRODIGI_API_KEY": prodigi_api_key,
                "EMAIL_SENDER": email_sender,
                "ORDERS_TABLE_NAME": orders_table.table_name
            }
        )

        # Create API Gateway
        api = apigw.RestApi(
            self, "PosterShopApi",
            rest_api_name="Poster Shop API",
            description="API for the Bauhaus Poster Shop"
        )

        # Add resources and methods
        checkout = api.root.add_resource("checkout")
        checkout.add_method(
            "POST",
            apigw.LambdaIntegration(create_checkout_lambda)
        )

        webhook = api.root.add_resource("webhook")
        webhook.add_method(
            "POST",
            apigw.LambdaIntegration(stripe_webhook_lambda)
        )

        # Grant permissions
        orders_table.grant_write_data(create_checkout_lambda)
        orders_table.grant_read_write_data(stripe_webhook_lambda)
        orders_table.grant_read_write_data(process_order_lambda)

        # Lambda: Prodigi Webhook (Shipping Updates)
        prodigi_webhook_lambda = _lambda.Function(
            self, "ProdigiWebhookLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="prodigi_webhook.handler",
            code=_lambda.Code.from_asset("backend"),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
                "EMAIL_SENDER": email_sender
            }
        )
        orders_table.grant_write_data(prodigi_webhook_lambda)

        # Lambda: Order Status (GET)
        order_status_lambda = _lambda.Function(
            self, "OrderStatusLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="order_status.handler",
            code=_lambda.Code.from_asset("backend"),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
            }
        )
        orders_table.grant_read_data(order_status_lambda)

        # API Gateway REST API
        api = apigw.RestApi(self, "BackendApi",
            rest_api_name="Backend Service",
            description="Handles Stripe checkout sessions, webhooks, and Prodigi order processing."
        )

        # /create-checkout-session endpoint
        create_checkout_resource = api.root.add_resource("create-checkout-session")
        create_checkout_resource.add_method("POST", apigw.LambdaIntegration(create_checkout_lambda))

        # /stripe-webhook endpoint
        stripe_webhook_resource = api.root.add_resource("stripe-webhook")
        stripe_webhook_resource.add_method("POST", apigw.LambdaIntegration(stripe_webhook_lambda))

        # /prodigi-webhook endpoint
        prodigi_webhook_resource = api.root.add_resource("prodigi-webhook")
        prodigi_webhook_resource.add_method("POST", apigw.LambdaIntegration(prodigi_webhook_lambda))

        # /order-status endpoint
        order_status_resource = api.root.add_resource("order-status")
        order_status_resource.add_method("GET", apigw.LambdaIntegration(order_status_lambda)) 