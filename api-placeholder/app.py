#!/usr/bin/env python3
import os
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer


PORT = int(os.getenv('PORT', 8080))


class JsonEcho(BaseHTTPRequestHandler):
    def send_json_response(self, **data):
        response = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-length', len(response))
        self.end_headers()
        self.wfile.write(response)

    def do_GET(self):
        logging.info(f'GET {self.path}')
        self.send_json_response(path=self.path, headers=dict(self.headers.items()))


def run(server_class=HTTPServer, handler_class=JsonEcho, port=8080):
    httpd = server_class(('', PORT), handler_class)
    logging.info('Starting API placeholder...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping API placeholder...')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run()
