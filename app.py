#!/usr/bin/env python3
import aws_cdk as cdk
from infrastructure.backend_stack import BackendStack
import os

app = cdk.App()

# Get environment variables
context = {
    "stripe_secret_key": os.environ.get("STRIPE_SECRET_KEY"),
    "stripe_webhook_secret": os.environ.get("STRIPE_WEBHOOK_SECRET"),
    "prodigi_api_key": os.environ.get("PRODIGI_API_KEY"),
    "email_sender": os.environ.get("EMAIL_SENDER"),
    "success_url": os.environ.get("SUCCESS_URL"),
    "cancel_url": os.environ.get("CANCEL_URL")
}

# Create the stack with context
BackendStack(app, "BackendStack", env=cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
    region=os.environ.get("CDK_DEFAULT_REGION")
), context=context)

app.synth() 