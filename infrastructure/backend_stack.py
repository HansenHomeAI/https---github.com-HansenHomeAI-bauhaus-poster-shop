from aws_cdk import (
    App,
    RemovalPolicy,
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    Duration,
    aws_events,
    aws_events_targets
)
from constructs import Construct

class BackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, context: dict, **kwargs) -> None:
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

        # Order Cleanup Lambda (runs weekly)
        order_cleanup_lambda = _lambda.Function(
            self, "OrderCleanupLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="order_cleanup.handler",
            code=_lambda.Code.from_asset("backend"),
            environment={
                "ORDERS_TABLE": orders_table.table_name,
            },
            timeout=Duration.seconds(60)  # Give it enough time to process all expired orders
        )

        # Add EventBridge rule to trigger the cleanup function weekly
        cleanup_rule = aws_events.Rule(
            self, "WeeklyCleanupRule",
            schedule=aws_events.Schedule.rate(Duration.days(7)),
            description="Triggers the order cleanup function weekly"
        )
        cleanup_rule.add_target(aws_events_targets.LambdaFunction(order_cleanup_lambda))

        # Grant permissions to the cleanup Lambda
        orders_table.grant_read_write_data(order_cleanup_lambda)

        # Create Lambda functions
        create_checkout_session = _lambda.Function(
            self, 'CreateCheckoutSession',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset('backend'),
            handler='checkout_session.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_test_secret_key'),
                'SUCCESS_URL': self.node.try_get_context('success_url'),
                'CANCEL_URL': self.node.try_get_context('cancel_url'),
                'ORDERS_TABLE': orders_table.table_name
            }
        )

        process_webhook = _lambda.Function(
            self, 'ProcessWebhook',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset('backend'),
            handler='process_webhook.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_test_secret_key'),
                'STRIPE_WEBHOOK_SECRET': self.node.try_get_context('stripe_webhook_secret'),
                'PRODIGI_API_KEY': self.node.try_get_context('prodigi_sandbox_api_key'),
                'ORDERS_TABLE': orders_table.table_name,
                'EMAIL_SENDER': self.node.try_get_context('email_sender')
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
                "EMAIL_SENDER": self.node.try_get_context('email_sender')
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
            create_checkout_session,
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
            apigw.LambdaIntegration(process_webhook)
        )

        # Add stripe test endpoint
        stripe_test_lambda = _lambda.Function(
            self, 'StripeTest',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset('backend'),
            handler='stripe_test.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_test_secret_key')
            }
        )
        
        stripe_test = api.root.add_resource("stripe-test")
        stripe_test.add_method(
            "GET",
            apigw.LambdaIntegration(stripe_test_lambda)
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
        orders_table.grant_write_data(create_checkout_session)
        orders_table.grant_read_write_data(process_webhook)
        orders_table.grant_write_data(prodigi_webhook_lambda)
        orders_table.grant_read_data(order_status_lambda) 