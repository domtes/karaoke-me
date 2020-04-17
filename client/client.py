'''
Simple command line client to remove vocals from audio/video tracks.
'''

import os
import json
import time

import click
import requests
from pygments import highlight, lexers, formatters


API_ENDPOINT_URL = os.getenv('API_ENDPOINT_URL')


def api_req(ctx: click.core.Context, method: str, url: str, **kwargs):
    method = method.lower()
    if method not in ['get', 'post']:
        raise ValueError(f'Unsupported HTTP method "{method}"')

    actual_url = ctx.obj['url'](url)

    if ctx.obj['verbose']:
        print(f'{method.upper()} {actual_url}')

    response = getattr(requests, method)(actual_url, **kwargs)

    if ctx.obj['verbose']:
        print(f'Server response status: {response.status_code}')
        echo_obj(response.json())

    return response


def api_get(ctx: click.core.Context, url: str, **kwargs):
    return api_req(ctx, 'GET', url, **kwargs)


def api_post(ctx: click.core.Context, url: str, **kwargs):
    return api_req(ctx, 'POST', url, **kwargs)


def highlight_json(obj):
    formatted_json = json.dumps(obj, sort_keys=True, indent=4)
    return highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())


def echo_obj(obj):
    click.echo(highlight_json(obj))


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enables verbose output.')
@click.option('--endpoint', '-e', default=API_ENDPOINT_URL, show_default=True)
@click.pass_context
def cli(ctx: click.core.Context, verbose: bool, endpoint: str):
    ctx.obj = {
        'verbose': verbose,
        'endpoint': endpoint,
        'url': lambda s: f'{endpoint}{s}'
    }


@cli.command('version')
@click.pass_context
def get_version(ctx: click.core.Context):
    '''Gets the service version'''
    response = api_get(ctx, '/')
    echo_obj(response.json())


@cli.command('list')
@click.pass_context
def list_jobs(ctx: click.core.Context):
    '''List conversion jobs'''
    response = api_get(ctx, '/jobs')
    echo_obj(response.json())


@cli.command('remove-vocals')
@click.option('--file', type=click.File(mode='rb'), required=True)
@click.option('--output-path', '-o', type=click.Path(writable=True))
@click.pass_context
def remove_vocals(ctx: click.core.Context, file: click.File, output_path: click.Path):
    '''Removes the vocal part from an audio/video file'''
    response = api_post(ctx, '/jobs')
    job = response.json()
    job_id = job['job_id']
    upload_data = job['upload_data']
    files = {'file': file}

    upload_started = time.time()
    response = requests.post(upload_data['url'],
        data=upload_data['fields'],
        files=files)

    upload_time = time.time() - upload_started
    print(f"File uploaded in {upload_time}s")

    response = api_post(ctx, f'/jobs/{job_id}/process')
    print(f'Processing file with job id {job_id}')

    processing_started = time.time()

    status_changed = False
    job = None
    while not status_changed:
        response = api_get(ctx, f'/jobs/{job_id}')

        job = response.json()
        status_changed = job['status'] != 'processing'
        time.sleep(5)

    processing_time = time.time() - processing_started
    print(f"File processed in {processing_time}s")

    response = requests.get(job['output_url'], stream=True)
    with open(output_path, 'wb') as f:
        for chunk in response.raw:
            f.write(chunk)

    print(f"Saved file to: {output_path}")


if __name__ == '__main__':
    cli()
