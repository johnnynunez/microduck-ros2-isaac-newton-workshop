"""Loopback HTTP unit tests (explicit fixture server; no physics claims)."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / 'ros_ws/src/microduck_gateway'))
from microduck_gateway.transport import SimHTTP


def test_http_private_endpoint_and_atomic_camera():
    for url in ('http://example.com:8766', 'http://192.168.1.1:8766', 'https://127.0.0.1:8766', 'http://localhost:8766', 'http://user:pass@127.0.0.1:8766'):
        with pytest.raises(ValueError):
            SimHTTP(url)
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            calls.append(self.path)
            self.send_response(200)
            self.send_header('X-Microduck-Episode', 'ep')
            self.send_header('X-Microduck-Sequence', '7')
            self.send_header('X-Microduck-Sim-Time', '1.25')
            self.send_header('X-Microduck-Capture-Monotonic', '10.5')
            self.end_headers()
            self.wfile.write(b'fixture-jpeg-not-a-real-sensor')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        data, meta = SimHTTP(f'http://127.0.0.1:{server.server_port}').camera()
        assert data == b'fixture-jpeg-not-a-real-sensor'
        assert meta == dict(episode='ep', sequence=7, sim_time=1.25, capture=10.5)
        assert calls == ['/v1/camera']
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_step_headers_reach_http_without_changing_body():
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            calls.append((self.path, dict(self.headers),
                          json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"accepted": true}')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    body = dict(episode_id='ep', request_id='step', expected_generation=3,
                vx=.1, vy=0, wz=0, duration_s=2)
    proof = {'X-Workshop-Observation-Episode': 'ep',
             'X-Workshop-Observation-Sequence': '8',
             'X-Workshop-Observation-Deadline': '100.5'}
    try:
        transport = SimHTTP(f'http://127.0.0.1:{server.server_port}')
        assert transport.post('/v1/step', body, 'private-token',
                              observation_headers=proof)['accepted']
        path, headers, received = calls[0]
        assert path == '/v1/step' and received == body
        assert {key: headers[key] for key in proof} == proof
        assert headers['X-Workshop-Lease'] == 'private-token'
        with pytest.raises(ValueError):
            transport.post('/v1/step', body, 'private-token',
                           observation_headers={**proof, 'X-Workshop-Lease': 'override'})
        assert len(calls) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
