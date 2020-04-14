#!/usr/bin/env python3

from aws_cdk import core

from karaokeme_cdk.karaokeme_cdk_stack import KaraokemeCdkStack


app = core.App()
KaraokemeCdkStack(app, "karaokeme-cdk")

app.synth()
