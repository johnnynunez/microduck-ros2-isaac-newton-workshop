"""No retries, redirects, proxies, DNS or physical endpoint selection."""
import http.client
import json
import math
from urllib.parse import urlsplit


class SimHTTP:
    def __init__(self, url='http://127.0.0.1:8766', timeout=.2):
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('simulation transport must be an uncredentialed numeric loopback HTTP endpoint')
        self.port = parsed.port or 8766
        self.timeout = timeout

    def request(self, method, path, body=None, token=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        headers = {'Content-Type': 'application/json'}
        if token is not None:
            headers['X-Workshop-Lease'] = token
        try:
            connection.request(method, path, body=None if body is None else json.dumps(body, allow_nan=False), headers=headers)
            response = connection.getresponse()
            payload = response.read(16 * 1024 * 1024 + 1)
            if len(payload) > 16 * 1024 * 1024 or response.status != 200:
                raise RuntimeError(f'simulation HTTP status {response.status}; payload withheld')
            return payload, dict((k.lower(), v) for k, v in response.getheaders())
        finally:
            connection.close()

    def get(self, path):
        return json.loads(self.request('GET', path)[0])

    def post(self, path, body, token=None):
        return json.loads(self.request('POST', path, body, token)[0])

    def camera(self):
        payload, headers = self.request('GET', '/v1/camera')
        meta = dict(episode=headers['x-microduck-episode'], sequence=int(headers['x-microduck-sequence']),
                    sim_time=float(headers['x-microduck-sim-time']), capture=float(headers['x-microduck-capture-monotonic']))
        if not all(math.isfinite(meta[k]) for k in ('sim_time', 'capture')):
            raise ValueError('nonfinite camera capture')
        return payload, meta
