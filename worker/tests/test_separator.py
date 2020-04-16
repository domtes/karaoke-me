import os

import boto3
import pytest
from moto import mock_s3

from separator import fetch_separate_and_upload, parse_s3_url


TEST_FILENAME = 'audio_example.mp3'


@pytest.fixture
def mocked_cloud():
    with mock_s3():
        s3 = boto3.resource('s3', region_name='eu-east-1')
        input_bucket = s3.create_bucket(Bucket='input')

        test_file_local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TEST_FILENAME)
        input_bucket.upload_file(Filename=test_file_local_path, Key=TEST_FILENAME)

        yield {
            's3': s3,
            'input_bucket': input_bucket,
            'output_bucket': s3.create_bucket(Bucket='output')
        }


def test_fetch_separate_and_upload(mocked_cloud):
    fetch_separate_and_upload('s3://input/audio_example.mp3', 's3://output/audio_example.mp3', s3=mocked_cloud['s3'])
    assert [e.key for e in mocked_cloud['output_bucket'].objects.all()] == ['audio_example.mp3']


@pytest.mark.parametrize('url,expected_result', [
    ('s3://bucket/key', ('bucket', 'key')),
    ('s3://bucket/with/deep/nested/path.ext', ('bucket', 'with/deep/nested/path.ext')),
])
def test_parse_s3_url(url, expected_result):
    assert parse_s3_url(url) == expected_result
