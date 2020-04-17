import os
import logging
import json
import sys
from collections import namedtuple
from tempfile import NamedTemporaryFile, TemporaryDirectory
from threading import Timer
from urllib.parse import urlparse

import boto3
from spleeter.separator import Separator
from spleeter.audio.adapter import get_audio_adapter


SPLEETER_CONFIGURATION = os.getenv('SPLEETER_CONFIGURATION', 'spleeter:2stems')
OUTPUT_CODEC = os.getenv('OUTPUT_CODEC', 'mp3')
OUTPUT_BITRATE = os.getenv('OUTPUT_BITRATE', '128k')
MAX_AUDIO_DURATION = float(os.getenv('MAX_AUDIO_DURATION', 600.))
AUDIO_START_OFFSET = float(os.getenv('AUDIO_START_OFFSET', 0.))
OUTPUT_FILENAME_FORMAT = os.getenv('OUTPUT_FILENAME_FORMAT', '{instrument}.{codec}')
QUEUE_NAME = os.getenv('QUEUE_NAME')
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', 10))
OUTPUT_BUCKET_NAME = os.getenv('OUTPUT_BUCKET_NAME')
OUTPUT_BUCKET_REGION= os.getenv('OUTPUT_BUCKET_REGION', 'eu-west-1')
TRACKS_TABLE_NAME = os.getenv('TRACKS_TABLE_NAME')
USE_MULTICHANNEL_WIENER_FILTERING = False


S3Entry = namedtuple('S3Entry', ['bucket_name', 'key'])


def parse_s3_url(s3_url: str) -> S3Entry:
    o = urlparse(s3_url)
    return S3Entry(o.netloc, o.path.lstrip('/'))


def fetch_separate_and_upload(input_s3_url, output_s3_url, s3=None):
    if s3 is None:
        s3 = boto3.resource("s3")

    with NamedTemporaryFile() as input_file, TemporaryDirectory() as output_path:
        input_object = s3.Object(**parse_s3_url(input_s3_url)._asdict())
        input_object.download_file(input_file.name)

        audio_adapter = get_audio_adapter(None)
        separator = Separator(
            SPLEETER_CONFIGURATION,
            MWF=USE_MULTICHANNEL_WIENER_FILTERING)

        separator.separate_to_file(
            input_file.name,
            output_path,
            audio_adapter=audio_adapter,
            offset=AUDIO_START_OFFSET,
            duration=MAX_AUDIO_DURATION,
            codec=OUTPUT_CODEC,
            bitrate=OUTPUT_BITRATE,
            filename_format=OUTPUT_FILENAME_FORMAT,
            synchronous=True)

        logging.info(f'Uploading output to: {output_s3_url}')
        output_object = s3.Object(**parse_s3_url(output_s3_url)._asdict())

        output_filename = os.path.join(output_path, f'accompaniment.{OUTPUT_CODEC}')
        output_object.upload_file(output_filename)


def poll_for_sqs_message(queue_name: str):
    sqs = boto3.client('sqs')
    queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
    response = sqs.receive_message(QueueUrl=queue_url)

    try:
        messages = response['Messages']
    except KeyError:
        logging.info('No messages in the queue')
        messages = []

    for message in messages:
        body = json.loads(message['Body'])
        job_id = body['job_id']
        output_s3_url = f"s3://{OUTPUT_BUCKET_NAME}/track_{job_id}.mp3"
        download_url = f'https://{OUTPUT_BUCKET_NAME}.s3-{OUTPUT_BUCKET_REGION}.amazonaws.com/track_{job_id}.mp3'
        logging.info(f'Start separating {job_id} -> {output_s3_url}')

        try:
            fetch_separate_and_upload(
                input_s3_url=body['input_s3_url'],
                output_s3_url=output_s3_url)

            logging.info(f'Processing successful: {output_s3_url}')

            dynamodb = boto3.client('dynamodb')
            dynamodb.update_item(
                TableName=TRACKS_TABLE_NAME,
                Key={'id': {'S': job_id}},
                AttributeUpdates={
                    'status': {'Value': {'S': 'successful'}},
                    'output_url': {'Value': {'S': download_url}}
                })
        except:
            logging.exception('Processing failed for some reason')
        finally:
            sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message['ReceiptHandle'])

    # Schedule the next poll operation
    Timer(POLLING_INTERVAL, poll_for_sqs_message, args=[queue_name]).start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    poll_for_sqs_message(QUEUE_NAME)
