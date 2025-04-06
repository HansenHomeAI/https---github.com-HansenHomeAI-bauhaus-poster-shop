#!/usr/bin/env python3
import os
import aws_cdk as cdk
from infrastructure.backend_stack import BackendStack

app = cdk.App()

# Get environment variables
stripe_secret_key = os.getenv('STRIPE_SECRET_KEY')
stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
prodigi_api_key = os.getenv('PRODIGI_API_KEY')
email_sender = os.getenv('EMAIL_SENDER')
success_url = os.getenv('SUCCESS_URL')
cancel_url = os.getenv('CANCEL_URL')

# Create the stack with environment variables
BackendStack(
    app, 
    "BackendStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION', 'us-west-2')
    ),
    stripe_secret_key=stripe_secret_key,
    stripe_webhook_secret=stripe_webhook_secret,
    prodigi_api_key=prodigi_api_key,
    email_sender=email_sender,
    success_url=success_url,
    cancel_url=cancel_url
)

app.synth() 