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
            code=_lambda.Code.from_asset(
                'backend',
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            handler='checkout_session.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_secret_key') or self.node.try_get_context('stripe_test_secret_key') or "sk_placeholder_value",
                'SUCCESS_URL': self.node.try_get_context('success_url') or 'https://hansenhomeai.github.io/success',
                'CANCEL_URL': self.node.try_get_context('cancel_url') or 'https://hansenhomeai.github.io/cancel',
                'ORDERS_TABLE': orders_table.table_name
            }
        )

        # Prodigi Order Lambda
        prodigi_order_lambda = _lambda.Function(
            self, "ProdigiOrderLambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="prodigi_order.handler",
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
                "PRODIGI_API_KEY": self.node.try_get_context('prodigi_sandbox_api_key') or "prod_sk_xxxxxxxxxxxxxxxxxxxxxxxx",
                "LOG_LEVEL": "DEBUG"  # Set to DEBUG for maximum logging
            },
            timeout=Duration.seconds(30)  # Give it enough time to process the API call
        )
        
        # Grant permissions for Prodigi Order Lambda
        orders_table.grant_read_write_data(prodigi_order_lambda)
        
        # Add SES permissions using an IAM policy statement
        ses_policy_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "ses:SendEmail",
                "ses:SendRawEmail"
            ],
            resources=["*"]  # You can restrict this to specific ARNs if desired
        )
        
        # Update ProcessWebhook Lambda to use SES
        process_webhook = _lambda.Function(
            self, 'ProcessWebhook',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(
                'backend',
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            handler='stripe_webhook.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_secret_key') or self.node.try_get_context('stripe_test_secret_key') or "sk_placeholder_value",
                'STRIPE_WEBHOOK_SECRET': self.node.try_get_context('stripe_webhook_secret') or "whsec_placeholder",
                'PRODIGI_API_KEY': self.node.try_get_context('prodigi_sandbox_api_key') or "prod_sk_xxxxxxxxxxxxxxxxxxxxxxxx",
                'ORDERS_TABLE': orders_table.table_name,
                'SES_SENDER_EMAIL': self.node.try_get_context('ses_sender_email') or 'hello@hansenhome.ai',
                'PRODIGI_ORDER_FUNCTION_NAME': prodigi_order_lambda.function_name,
                'LOG_LEVEL': 'DEBUG'
            },
            timeout=Duration.seconds(30)  # Give enough time to process the webhook
        )
        
        # Add SES permissions to the webhook Lambda
        process_webhook.add_to_role_policy(ses_policy_statement)
        
        # Add permissions to invoke the Prodigi Order Lambda function
        lambda_invoke_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["lambda:InvokeFunction"],
            resources=[prodigi_order_lambda.function_arn]
        )
        process_webhook.add_to_role_policy(lambda_invoke_policy)

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
                "SES_SENDER_EMAIL": self.node.try_get_context('ses_sender_email') or 'hello@hansenhome.ai'
            }
        )
        
        # Add SES permissions to prodigi webhook Lambda
        prodigi_webhook_lambda.add_to_role_policy(ses_policy_statement)

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

        # Define CORS options
        cors_options = apigw.CorsOptions(
            allow_origins=["https://hansenhomeai.github.io"],
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"]
        )

        # Create API Gateway
        api = apigw.RestApi(
            self, 'PosterShopApi',
            rest_api_name='BauhausPosterShopAPI',
            description='API for Bauhaus Poster Shop',
            default_cors_preflight_options=cors_options
        )

        # Add checkout endpoint
        checkout = api.root.add_resource("checkout")
        checkout_integration = apigw.LambdaIntegration(
            create_checkout_session,
            proxy=True,
            integration_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': "'https://hansenhomeai.github.io'",
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
            code=_lambda.Code.from_asset(
                'backend',
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            handler='stripe_test.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_test_secret_key') or "sk_placeholder_value"
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

        # Payment Success Lambda
        payment_success_lambda = _lambda.Function(
            self, 'PaymentSuccessLambda',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(
                'backend',
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            handler='payment_success.handler',
            environment={
                'STRIPE_SECRET_KEY': self.node.try_get_context('stripe_test_secret_key') or self.node.try_get_context('stripe_secret_key') or "sk_placeholder_value",
                'PRODIGI_API_KEY': self.node.try_get_context('prodigi_sandbox_api_key') or "prod_sk_xxxxxxxxxxxxxxxxxxxxxxxx",
                'ORDERS_TABLE': orders_table.table_name,
                'SES_SENDER_EMAIL': self.node.try_get_context('ses_sender_email') or 'hello@hansenhome.ai'
            }
        )
        
        # Add SES permissions to payment success Lambda
        payment_success_lambda.add_to_role_policy(ses_policy_statement)

        # Add payment-success endpoint with CORS enabled
        payment_success = api.root.add_resource("payment-success")
        payment_success_integration = apigw.LambdaIntegration(
            payment_success_lambda,
            proxy=True,
            integration_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': "'https://hansenhomeai.github.io'",
                    'method.response.header.Access-Control-Allow-Headers': "'*'",
                    'method.response.header.Access-Control-Allow-Methods': "'OPTIONS,POST'"
                }
            }]
        )
        
        payment_success.add_method(
            "POST",
            payment_success_integration,
            method_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': True,
                    'method.response.header.Access-Control-Allow-Headers': True,
                    'method.response.header.Access-Control-Allow-Methods': True
                }
            }]
        )

        # Payment Status Lambda
        payment_status_lambda = _lambda.Function(
            self, 'PaymentStatusLambda',
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(
                'backend',
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_9.bundling_image,
                    "command": [
                        "bash", "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output"
                    ]
                }
            ),
            handler='payment_status.handler',
            environment={
                'ORDERS_TABLE': orders_table.table_name
            }
        )

        # Add payment-status endpoint with CORS enabled
        payment_status = api.root.add_resource("payment-status")
        payment_status_integration = apigw.LambdaIntegration(
            payment_status_lambda,
            proxy=True,
            integration_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': "'https://hansenhomeai.github.io'",
                    'method.response.header.Access-Control-Allow-Headers': "'*'",
                    'method.response.header.Access-Control-Allow-Methods': "'OPTIONS,GET'"
                }
            }]
        )
        
        payment_status.add_method(
            "GET",
            payment_status_integration,
            method_responses=[{
                'statusCode': '200',
                'responseParameters': {
                    'method.response.header.Access-Control-Allow-Origin': True,
                    'method.response.header.Access-Control-Allow-Headers': True,
                    'method.response.header.Access-Control-Allow-Methods': True
                }
            }]
        )

        # Grant permissions
        orders_table.grant_write_data(create_checkout_session)
        orders_table.grant_read_write_data(process_webhook)
        orders_table.grant_write_data(prodigi_webhook_lambda)
        orders_table.grant_read_data(order_status_lambda)
        orders_table.grant_read_data(payment_status_lambda)  # Grant permissions to payment status Lambda
        orders_table.grant_read_write_data(payment_success_lambda)  # Grant permissions to payment success Lambda

        # Add logging configuration function
        def add_enhanced_logging(lambda_function):
            """Add enhanced CloudWatch logging for Lambda functions"""
            lambda_function.add_environment("LOG_LEVEL", "INFO")
            lambda_function.add_environment("POWERTOOLS_SERVICE_NAME", "poster-shop")
            lambda_function.add_environment("POWERTOOLS_LOGGER_SAMPLE_RATE", "1.0")
            lambda_function.add_environment("POWERTOOLS_LOGGER_LOG_EVENT", "true")
            
        # Apply enhanced logging to all Lambda functions
        add_enhanced_logging(order_cleanup_lambda)
        add_enhanced_logging(create_checkout_session)
        add_enhanced_logging(process_webhook)
        add_enhanced_logging(prodigi_webhook_lambda)
        add_enhanced_logging(order_status_lambda)
        add_enhanced_logging(payment_success_lambda)
        add_enhanced_logging(payment_status_lambda)
        add_enhanced_logging(prodigi_order_lambda) 