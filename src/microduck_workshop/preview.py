"""Read-only, SDK-independent browser preview. No robot control is exposed."""

import argparse
import json
import math
import re
import socket
import threading
import time
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files

UPSTREAMS = {"http://127.0.0.1:8766", "http://localhost:8766"}
ASSETS = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "text/javascript"),
    "/style.css": ("style.css", "text/css"),
}


MAX_STATUS_BYTES = 64 * 1024
MAX_JPEG_BYTES = 8 * 1024 * 1024
FRAME_ROUTES = {"/head.jpg": "/v1/camera", "/overview.jpg": "/v1/overview"}
FRAME_HEADERS = tuple(
    "X-Microduck-" + suffix for suffix in ("Episode", "Sequence", "Sim-Time", "Capture-Monotonic")
)
STALE_AFTER_S = 0.5
UPSTREAM_TIMEOUT_S = 1.0
STATUS_FIELDS = ("protocol_version", "ready", "physics", "episode_id", "generation", "sim_time")


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid number")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("invalid identifier")
    return value


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def invalid_constant(value):
    raise ValueError("nonfinite JSON")


def finite_json_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite JSON")
    return result


def public_status(body):
    data = json.loads(
        body,
        object_pairs_hook=unique_object,
        parse_constant=invalid_constant,
        parse_float=finite_json_float,
    )
    if not isinstance(data, dict):
        raise TypeError("status must be an object")
    status = {key: data[key] for key in STATUS_FIELDS}
    if type(status["protocol_version"]) is not int or status["protocol_version"] != 1:
        raise ValueError("unsupported protocol")
    if type(status["ready"]) is not bool or status["physics"] != "newton":
        raise ValueError("invalid runtime status")
    identifier(status["episode_id"])
    if type(status["generation"]) is not int or not 0 <= status["generation"] <= 2**53 - 1:
        raise ValueError("invalid generation")
    number(status["sim_time"])
    return json.dumps(status, allow_nan=False).encode()


def frame_headers(headers, body):
    if headers.get_content_type() != "image/jpeg" or not (
        body.startswith(b"\xff\xd8") and body.endswith(b"\xff\xd9")
    ):
        raise ValueError("not a JPEG")
    values = {}
    for key in FRAME_HEADERS:
        items = headers.get_all(key, [])
        if len(items) != 1 or not 1 <= len(items[0]) <= 64:
            raise ValueError("missing or ambiguous provenance")
        values[key] = items[0]
    identifier(values[FRAME_HEADERS[0]])
    sequence = values[FRAME_HEADERS[1]]
    if not re.fullmatch(r"[0-9]{1,16}", sequence) or int(sequence) > 2**53 - 1:
        raise ValueError("invalid sequence")
    for key in FRAME_HEADERS[2:]:
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?", values[key]):
            raise ValueError("invalid timestamp")
        number(float(values[key]))
    age = time.monotonic() - float(values[FRAME_HEADERS[3]])
    if age < 0:
        raise ValueError("capture clock must be on the same host")
    values["X-Preview-Age-S"] = f"{age:.6f}"
    values["X-Preview-State"] = "stale" if age > STALE_AFTER_S else "fresh"
    return values


def fetch(path, limit):
    # Literal loopback also for the accepted 'localhost' spelling: no DNS, proxies or redirects.
    connection = HTTPConnection("127.0.0.1", 8766, timeout=UPSTREAM_TIMEOUT_S)
    deadline = time.monotonic() + UPSTREAM_TIMEOUT_S
    timer = None
    try:
        connection.connect()
        upstream_socket = connection.sock

        def expire():
            # Shutdown interrupts even a slow-drip header/body read. close() alone does not.
            try:
                upstream_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        with connection.getresponse() as response:
            if response.status != 200:
                raise ValueError("source unavailable")
            body = response.read(limit + 1)
            if len(body) > limit or time.monotonic() >= deadline:
                raise ValueError("source response exceeded budget")
            return response.headers, body
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


class PreviewHandler(BaseHTTPRequestHandler):
    """Exact-path GET handler; never forward client headers, bodies or URLs."""

    def log_message(self, format, *args):
        # Do not log arbitrary incoming paths/headers or upstream internals.
        pass

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self.method_not_allowed
        raise AttributeError(name)

    def send_body(self, status, body, content_type="text/plain", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' blob:; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'none'",
        )
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def method_not_allowed(self):
        self.close_connection = True
        self.send_body(405, b"GET only\n", headers={"Allow": "GET"})

    def do_GET(self):
        # BaseHTTPRequestHandler normalizes leading //, so inspect the request target too.
        target = self.requestline.split()[1]
        if target == "/status" or target in FRAME_ROUTES:
            try:
                if target == "/status":
                    headers, body = fetch("/v1/health", MAX_STATUS_BYTES)
                    if headers.get_content_type() != "application/json":
                        raise ValueError("invalid content type")
                    self.send_body(200, public_status(body), "application/json")
                else:
                    headers, body = fetch(FRAME_ROUTES[target], MAX_JPEG_BYTES)
                    self.send_body(200, body, "image/jpeg", frame_headers(headers, body))
            except (
                OSError,
                HTTPException,
                ValueError,
                TypeError,
                KeyError,
                OverflowError,
                RecursionError,
            ):
                self.send_body(503, b"Source unavailable or invalid\n")
            return
        if target not in ASSETS:
            self.send_body(404, b"Not found\n")
            return
        name, mime = ASSETS[target]
        self.send_body(
            200,
            files("microduck_workshop").joinpath("web", name).read_bytes(),
            mime + "; charset=utf-8",
        )


def create_server(*, upstream="http://127.0.0.1:8766", bind="127.0.0.1", port=8765):
    if upstream not in UPSTREAMS:
        raise ValueError("upstream must be http://127.0.0.1:8766 or http://localhost:8766")
    return ThreadingHTTPServer((bind, port), PreviewHandler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="http://127.0.0.1:8766")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        server = create_server(upstream=args.upstream, bind=args.bind, port=args.port)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Read-only preview: http://{args.bind}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
