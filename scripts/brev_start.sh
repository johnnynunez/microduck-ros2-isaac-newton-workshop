#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --accept-nvidia-eula ]]; then
  echo 'Review NVIDIA terms; use --accept-nvidia-eula.' >&2
  exit 2
fi
bash scripts/brev_preflight.sh
# Start the selected model first, per docs/local_model.md. Do not reserve the
# one-shot ROS control lease until weights and actual model serving are ready.
python3 - <<'PY'
import json, os, urllib.request
port = int(os.environ.get('MODEL_PORT', '8080'))
assert 1024 <= port <= 65535, 'MODEL_PORT must be 1024..65535'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(f'http://127.0.0.1:{port}/v1/models', timeout=5) as r:
    models = json.load(r)
assert any(m.get('id') == 'qwen3.8-27b' for m in models.get('data', [])), 'Classroom Qwen model not loaded; follow docs/local_model.md'
PY
bash scripts/sim_start.sh "$@"
trap 'bash scripts/brev_stop.sh' ERR INT TERM
docker compose up -d --no-build ros preview
python3 - <<'PY'
import time, urllib.request
for _ in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/', timeout=2) as r:
            assert r.status == 200
        break
    except (OSError, AssertionError):
        time.sleep(.5)
else:
    raise SystemExit('Read-only preview failed to start; inspect docker compose logs preview')
PY
# No agent is run automatically; students explicitly run the selected exercise.
docker compose ps
printf '%s\n' 'Check the real live ROS observe service before running CASCADE; a running container is not perception acceptance.'
trap - ERR INT TERM
