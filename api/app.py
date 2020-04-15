import os
import json
from uuid import uuid4

import boto3
from flask import Flask, request


APP_NAME = 'karaoke-http-api'
VERSION = '0.10'
PROCESSING_QUEUE_URL = os.getenv('PROCESSING_QUEUE_URL')
TRACKS_TABLE_NAME = os.getenv('TRACKS_TABLE_NAME')
UPLOAD_BUCKET_NAME = os.getenv('UPLOAD_BUCKET_NAME')
UPLOAD_AUTH_TIMEOUT = int(os.getenv('UPLOAD_AUTH_TIMEOUT', 120))
app = Flask(__name__)


def get_dynamodb_client():
    return boto3.client('dynamodb')


def get_s3_client():
    return boto3.client('s3')


def get_sqs_client():
    return boto3.client('sqs')


def strip_dynamodb_type_tags(obj):
    return {key: list(value.values())[0]
        for key, value in obj.items()}


@app.route('/')
def info():
    return dict(name=APP_NAME, version=VERSION)


@app.route('/jobs', methods=['GET', 'POST'])
def jobs_resource():
    dynamodb = get_dynamodb_client()
    if request.method == 'POST':
        job_id = str(uuid4())

        s3_key = f'track_{job_id}'
        s3_complete_url = f's3://{UPLOAD_BUCKET_NAME}/{s3_key}'

        dynamodb.put_item(
            TableName=TRACKS_TABLE_NAME,
            Item={
                'id': {'S': job_id},
                'input_s3_url': {'S': s3_complete_url},
                'status': {'S': 'uploading'}
            })

        # create the pre-signed upload URL
        s3 = get_s3_client()
        upload_data = s3.generate_presigned_post(UPLOAD_BUCKET_NAME, s3_key,
            Fields=None,
            Conditions=None,
            ExpiresIn=UPLOAD_AUTH_TIMEOUT)

        return dict(job_id=job_id, upload_data=upload_data)

    response = dynamodb.scan(TableName=TRACKS_TABLE_NAME)
    return dict(items=[strip_dynamodb_type_tags(el) for el in response['Items']],
                count=response['Count'],
                scanned_count=response['ScannedCount'])


@app.route('/jobs/<job_id>', methods=['GET'])
def get_job_details(job_id):
    dynamodb = get_dynamodb_client()
    response = dynamodb.get_item(TableName=TRACKS_TABLE_NAME, Key={'id': {'S': job_id}})
    return strip_dynamodb_type_tags(response['Item'])


@app.route('/jobs/<job_id>/process', methods=['POST'])
def trigger_job_processing(job_id):
    dynamodb = get_dynamodb_client()
    response = dynamodb.get_item(TableName=TRACKS_TABLE_NAME, Key={'id': {'S': job_id}})
    job = strip_dynamodb_type_tags(response['Item'])

    if job['status'] != 'uploading':
        return dict(status='failed', message='Job is in a wrong state'), 400

    dynamodb.update_item(
        TableName=TRACKS_TABLE_NAME,
        Key={'id': {'S': job_id}},
        AttributeUpdates={
            'status': {'Value': {'S': 'processing'}}
        })

    sqs = get_sqs_client()
    response = sqs.send_message(
        QueueUrl=PROCESSING_QUEUE_URL,
        MessageBody=json.dumps({
            'job_id': job['id'],
            'input_s3_url': job['input_s3_url']}))

    return dict(status='processing', message_id=response['MessageId'])
