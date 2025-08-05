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


def test_verify_tools_success(capsys):
    data = {"tools": [{"name": name} for name in verify_tools.EXPECTED_TOOLS]}
    with fake_server(data) as url:
        assert verify_tools.verify(url)
    out = capsys.readouterr().out
    assert out.strip() == "All expected tools present."


def test_verify_tools_missing(capsys):
    missing = sorted(verify_tools.EXPECTED_TOOLS)[0]
    remaining = sorted(verify_tools.EXPECTED_TOOLS - {missing})
    data = {"tools": [{"name": name} for name in remaining]}
    with fake_server(data) as url:
        assert not verify_tools.verify(url)
    out = capsys.readouterr().out
    assert f"Missing tools: {missing}" in out
    assert "Server tool list:" in out
    start = out.index("[")
    tools_json = out[start:]
    assert json.loads(tools_json) == [{"name": name} for name in remaining]


def test_verify_tools_allow_superset(capsys):
    data = {"tools": [{"name": name} for name in verify_tools.EXPECTED_TOOLS] + [{"name": "extra_tool"}]}
    with fake_server(data) as url:
        assert verify_tools.verify(url, allow_superset=True)
    out = capsys.readouterr().out
    assert out.strip() == "All expected tools present."
