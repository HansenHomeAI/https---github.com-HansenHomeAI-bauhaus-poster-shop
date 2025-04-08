#!/usr/bin/env python3
import os
from aws_cdk import App, Environment
from infrastructure.backend_stack import BackendStack

app = App()

context = {
    'stripe_test_secret_key': os.environ.get('STRIPE_TEST_SECRET_KEY'),
    'stripe_webhook_secret': os.environ.get('STRIPE_WEBHOOK_SECRET'),
    'prodigi_sandbox_api_key': os.environ.get('PRODIGI_SANDBOX_API_KEY'),
    'email_sender': os.environ.get('EMAIL_SENDER'),
    'success_url': os.environ.get('SUCCESS_URL', 'https://hansenhomeai.github.io/success'),
    'cancel_url': os.environ.get('CANCEL_URL', 'https://hansenhomeai.github.io/cancel')
}

BackendStack(app, "BauhausPosterShopStack", context)

app.synth() 