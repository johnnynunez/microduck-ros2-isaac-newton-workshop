#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/brev_preflight.sh
# Start simulator through its documented owner first. No reset/re-arm is automated here.
curl --fail --silent --show-error --max-time 3 http://127.0.0.1:8766/v1/health | python3 -c 'import json,sys; h=json.load(sys.stdin); assert h.get("ready") is True and h.get("physics")=="newton" and h.get("protocol_version")==1, "Real Newton protocol v1 is not ready"'
docker compose up -d --no-build ros
docker compose ps
