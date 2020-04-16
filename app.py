#!/usr/bin/env python3

import os

from aws_cdk import core
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_sqs as sqs

from karaokeme_cdk.karaokeme_cdk_stack import KaraokemeCdkStack


class BaseResources(core.Stack):
    def __init__(self, *args, **kwargs):
        super(BaseResources, self).__init__(*args, **kwargs)

        # Network
        self.vpc = ec2.Vpc(self, 'karaoke-vpc')

        # ECS cluster
        self.cluster = ecs.Cluster(self, 'karaoke-cluster',
            vpc=self.vpc)

        # DynamoDB table
        self.tracks_table = dynamodb.Table(self, 'karaoke-tracks-table',
            table_name='karaoke-tracks',
            partition_key=dynamodb.Attribute(name='id', type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST)

        # The bucket where uploaded files will be kept
        self.input_bucket = s3.Bucket(self, 'input-bucket',
            bucket_name='karaoke-uploaded-tracks')

        # The bucket where processed files will be kept and served back to the public
        self.output_bucket = s3.Bucket(self, 'output-bucket',
            bucket_name='karaoke-separated-tracks',
            public_read_access=True)


class HttpApi(core.Stack):
    def __init__(self, scope, id,
                 cluster: ecs.Cluster,
                 tracks_table: dynamodb.Table,
                 processing_queue: sqs.Queue,
                 upload_bucket: s3.Bucket,
                 **kwargs):
        super().__init__(scope, id, **kwargs)

        api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'api'))

        self.api = ecs_patterns.ApplicationLoadBalancedFargateService(self, 'http-api-service',
            cluster=cluster,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_asset(directory=api_dir),
                container_port=8080,
                environment={
                    'PROCESSING_QUEUE_URL': processing_queue.queue_url,
                    'TRACKS_TABLE_NAME': tracks_table.table_name,
                    'UPLOAD_BUCKET_NAME': upload_bucket.bucket_name
                }),
            desired_count=2,
            cpu=256,
            memory_limit_mib=512)

        processing_queue.grant_send_messages(self.api.service.task_definition.task_role)
        tracks_table.grant_read_write_data(self.api.service.task_definition.task_role)
        upload_bucket.grant_put(self.api.service.task_definition.task_role)


class SeparatorWorker(core.Stack):
    def __init__(self, scope, id,
                 cluster: ecs.Cluster,
                 tracks_table: dynamodb.Table,
                 input_bucket: s3.Bucket,
                 output_bucket: s3.Bucket,
                 **kwargs):
        super().__init__(scope, id, **kwargs)

        worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'worker'))

        self.service = ecs_patterns.QueueProcessingFargateService(self, 'separator-service',
            cluster=cluster,
            cpu=2048,
            memory_limit_mib=8192,
            image=ecs.ContainerImage.from_asset(directory=worker_dir),
            environment={
                'TRACKS_TABLE_NAME': tracks_table.table_name,
                'OUTPUT_BUCKET_NAME': output_bucket.bucket_name
            })

        input_bucket.grant_read(self.service.task_definition.task_role)
        output_bucket.grant_write(self.service.task_definition.task_role)
        tracks_table.grant_read_write_data(self.service.task_definition.task_role)


class KaraokeApp(core.App):
    def __init__(self, *args, **kwargs):
        super(KaraokeApp, self).__init__(*args, **kwargs)

        self.base_resources = BaseResources(self, 'base-resources')

        self.separator_worker = SeparatorWorker(self, 'separator-worker',
            cluster=self.base_resources.cluster,
            input_bucket=self.base_resources.input_bucket,
            output_bucket=self.base_resources.output_bucket,
            tracks_table=self.base_resources.tracks_table)

        self.http_api = HttpApi(self, 'http-api',
            cluster=self.base_resources.cluster,
            processing_queue=self.separator_worker.service.sqs_queue,
            tracks_table=self.base_resources.tracks_table,
            upload_bucket=self.base_resources.input_bucket)


app = KaraokeApp()
app.synth()
