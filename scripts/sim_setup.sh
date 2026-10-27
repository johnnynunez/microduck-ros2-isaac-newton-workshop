#!/usr/bin/env bash
# Public software + explicit asset admission + real Kit camera/groundplane warmup.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --accept-nvidia-eula || "${2:-}" != --accept-mesh-license ]]; then
  echo 'Review NVIDIA and Pollen terms; pass --accept-nvidia-eula --accept-mesh-license explicitly.' >&2
  exit 2
fi
export OMNI_KIT_ACCEPT_EULA=YES
mkdir -p .workshop/receipts .workshop/sim-home .workshop/sim-output .cache/assets
# Resource flags cap BuildKit; heavyrun alone cannot cap dockerd children.
cache_args=()
if [[ -n "${WORKSHOP_UV_CACHE:-}" ]]; then
  cache_args=(--build-context "download-cache=$WORKSHOP_UV_CACHE")
fi
docker build "${cache_args[@]}" --resource memory=32g --resource cpu-quota=800000 \
  --target sim -f docker/sim.Dockerfile -t "${WORKSHOP_SIM_IMAGE:-roscon/microduck-sim:local}" .
docker image inspect "${WORKSHOP_SIM_IMAGE:-roscon/microduck-sim:local}" \
  --format '{{json .}}' > .workshop/receipts/sim-image.json
docker run --rm --name roscon-brev-assets --memory=4g --cpus=4 \
  -v "$PWD/.cache/assets:/assets:rw" "${WORKSHOP_SIM_IMAGE:-roscon/microduck-sim:local}" \
  -m microduck_workshop.assets fetch --accept-mesh-license --destination /assets \
  | tee .workshop/receipts/assets.json
python3 - <<'PY'
import socket
with socket.socket() as s:
    s.bind(('127.0.0.1', 8766))  # refuse another simulator, never use its episode
PY
# Warm vendor groundplane/MDL, converter, Warp, both cameras and Pillow JPEG.
# Kit can exit zero on startup failure: require explicit runtime and pixel receipts.
if [[ -d .workshop/sim-output/warmup ]]; then
  mv .workshop/sim-output/warmup ".workshop/sim-output/warmup-$(date -u +%Y%m%dT%H%M%S)-$$"
fi
cleanup() {
  docker logs roscon-brev-warmup > .workshop/receipts/sim-warmup.log 2>&1 || true
  docker stop --time 8 roscon-brev-warmup >/dev/null 2>&1 || true
  docker rm roscon-brev-warmup >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker compose run -d --no-deps --name roscon-brev-warmup sim \
  -m microduck_workshop.sim.play --asset-root /assets --mode serve --cameras \
  --steps 200 --tag-id 0 --output /outputs/warmup
python3 - <<'PY'
import json, subprocess, time, urllib.request
from pathlib import Path
out = Path('.workshop/receipts')
for attempt in range(2400):
    if subprocess.check_output(['docker','inspect','-f','{{.State.Running}}','roscon-brev-warmup'], text=True).strip() != 'true':
        raise SystemExit('Warmup exited before producing a head JPEG; inspect sim-warmup.log')
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766/v1/camera', timeout=2) as r:
            jpeg = r.read()
            assert jpeg.startswith(b'\xff\xd8') and len(jpeg) > 1000
            (out / 'head.jpg').write_bytes(jpeg)
            (out / 'head-headers.json').write_text(json.dumps(dict(r.headers), indent=2))
        break
    except (OSError, AssertionError):
        time.sleep(.25)
else:
    raise SystemExit('No actual head JPEG after camera warmup deadline')
PY
timeout 180 docker wait roscon-brev-warmup
docker logs roscon-brev-warmup > .workshop/receipts/sim-warmup.log 2>&1
python3 - <<'PY'
import json
from pathlib import Path
p = Path('.workshop/sim-output/warmup')
r = json.loads((p / 'evaluation.json').read_text())
assert r['control_steps'] == 200 and r['physics_steps'] > 0
assert r['runtime']['isaacsim'] == '6.2.0.0'
assert r['runtime']['newton'] == '1.6.1'
assert Path('.workshop/receipts/head.jpg').is_file(), 'real camera/JPEG warmup missing'
print('REAL_SIM_WARMUP_PASS', r['runtime'])
PY
