#!/usr/bin/env bash
# An explicit operator action starts one NEW zero-intent episode; never auto-rearm.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --accept-nvidia-eula ]]; then
  echo 'Review NVIDIA terms; pass --accept-nvidia-eula to start an episode.' >&2
  exit 2
fi
export OMNI_KIT_ACCEPT_EULA=YES
if [[ "$(docker inspect -f '{{.State.Running}}' roscon-brev-sim 2>/dev/null || true)" == true ]]; then
  echo 'Simulator already running. Refusing restart/re-arm; use brev_stop.sh first.' >&2
  exit 2
fi
python3 - <<'PY'
import socket
with socket.socket() as s:
    # Match the HTTP server: TIME_WAIT after shutdown is not a live listener.
    # A socket actively listening on this address still makes bind fail.
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', 8766))
PY
mkdir -p .workshop/sim-home .workshop/sim-output .workshop/receipts
# Preserve previous episode evidence. No reset or motion command is issued here.
if [[ -d .workshop/sim-output/episode ]]; then
  mv .workshop/sim-output/episode ".workshop/sim-output/episode-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
trap 'docker compose stop --timeout 8 sim >/dev/null 2>&1 || true' ERR INT TERM
docker compose up -d --no-build sim
python3 - <<'PY'
import json, subprocess, time, urllib.request
from pathlib import Path
for _ in range(600):
    if subprocess.check_output(['docker','inspect','-f','{{.State.Running}}','roscon-brev-sim'], text=True).strip() != 'true':
        raise SystemExit('Simulator exited; inspect docker compose logs sim')
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/v1/health', timeout=2) as r:
            h = json.load(r)
        assert h['ready'] and h['physics'] == 'newton' and h['protocol_version'] == 1
        assert h['runtime']['isaacsim'] == '6.2.0.0' and h['runtime']['newton'] == '1.6.1'
        with urllib.request.urlopen('http://127.0.0.1:8766/v1/camera', timeout=2) as r:
            assert r.read().startswith(b'\xff\xd8')
        Path('.workshop/receipts/live-health.json').write_text(json.dumps(h, indent=2))
        print('Real simulator and head JPEG ready; episode:', h['episode_id'])
        break
    except (OSError, AssertionError, KeyError):
        time.sleep(1)
else:
    raise SystemExit('Simulator readiness deadline exceeded')
PY
trap - ERR INT TERM
