"""Exercise real Linux TIME_WAIT and active-listener protection, without a GPU."""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import socket
from threading import Thread
import urllib.request


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'OK')


def main():
    server = HTTPServer(('127.0.0.1', 0), Handler)
    address = server.server_address
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(address)
        except OSError:
            active_listener_refused = True
        else:
            raise AssertionError('active listener was not protected')
    worker = Thread(target=server.handle_request)
    worker.start()
    with urllib.request.urlopen(f'http://{address[0]}:{address[1]}') as response:
        assert response.read() == b'OK'
    worker.join(timeout=5)
    assert not worker.is_alive()
    server.server_close()
    plain_failed = False
    with socket.socket() as probe:
        try: probe.bind(address)
        except OSError: plain_failed = True
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(address)
    print(json.dumps({'active_listener_refused': active_listener_refused,
                      'plain_probe_failed_after_close': plain_failed,
                      'reuse_probe_passed': True}))


if __name__ == '__main__': main()
