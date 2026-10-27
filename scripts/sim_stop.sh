#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Only stop this deployment's simulator. Do not send stop to an unrelated loopback server.
if [[ "$(docker inspect -f '{{.State.Running}}' roscon-brev-sim 2>/dev/null || true)" == true ]]; then
  python3 - <<'PY' || true
import json, urllib.request
with urllib.request.urlopen('http://127.0.0.1:8766/v1/health', timeout=2) as r:
    episode = json.load(r)['episode_id']
req = urllib.request.Request('http://127.0.0.1:8766/v1/stop',
    data=json.dumps({'episode_id': episode, 'latch': True}).encode(),
    headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req, timeout=2) as r:
    print('Stop intent response (not physical-rest proof):', r.read().decode())
PY
fi
docker compose stop --timeout 10 sim
