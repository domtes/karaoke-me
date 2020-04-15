#!/usr/bin/env python3

import os

from aws_cdk import core
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns

from karaokeme_cdk.karaokeme_cdk_stack import KaraokemeCdkStack


class BaseResources(core.Stack):
    def __init__(self, *args, **kwargs):
        super(BaseResources, self).__init__(*args, **kwargs)

        # Network
        self.vpc = ec2.Vpc(self, 'karaoke-vpc')

        # ECS cluster
        self.cluster = ecs.Cluster(self, 'karaoke-cluster',
            vpc=self.vpc)


class HttpApi(core.Stack):
    def __init__(self, scope, id, cluster: ecs.Cluster,  **kwargs):
        super().__init__(scope, id, **kwargs)

        api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'api-placeholder'))

        self.api = ecs_patterns.ApplicationLoadBalancedFargateService(self, 'http-api-service',
            cluster=cluster,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(directory=api_dir),
                container_port=8080),
            desired_count=2,
            cpu=256,
            memory_limit_mib=512)


class SeparatorWorker(core.Stack):
    def __init__(self, scope, id, cluster: ecs.Cluster, **kwargs):
        super().__init__(scope, id, **kwargs)

        worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'worker-placeholder'))

        self.service = ecs_patterns.QueueProcessingFargateService(self, 'separator-service',
            cpu=256,
            memory_limit_mib=512,
            image=ecs.ContainerImage.from_asset(directory=worker_dir),
            cluster=cluster)


class KaraokeApp(core.App):
    def __init__(self, *args, **kwargs):
        super(KaraokeApp, self).__init__(*args, **kwargs)

        self.base_resources = BaseResources(self, 'base-resources')

        self.http_api = HttpApi(self, 'http-api',
            cluster=self.base_resources.cluster)

        self.separator_worker = SeparatorWorker(self, 'separator-worker',
            cluster=self.base_resources.cluster)


app = KaraokeApp()
app.synth()
