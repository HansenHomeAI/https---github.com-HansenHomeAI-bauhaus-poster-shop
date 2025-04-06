#!/usr/bin/env python3
import aws_cdk as cdk
from infrastructure.backend_stack import BackendStack

app = cdk.App()
BackendStack(app, "BackendStack")
app.synth() 