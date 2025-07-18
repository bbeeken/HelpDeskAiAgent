import json
import threading
from contextlib import contextmanager
from http.server import HTTPServer, BaseHTTPRequestHandler

import verify_tools


@contextmanager
def fake_server(data):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/tools":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            else:
                self.send_error(404)

        def log_request(self, *args, **kwargs):
            pass

    server = HTTPServer(("localhost", 0), Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://localhost:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()


def test_verify_tools_success():
    data = {"tools": [{"name": "g_ticket"}, {"name": "l_tickets"}]}
    with fake_server(data) as url:
        assert verify_tools.verify(url)


def test_verify_tools_missing():
    data = {"tools": [{"name": "g_ticket"}]}
    with fake_server(data) as url:
        assert not verify_tools.verify(url)
