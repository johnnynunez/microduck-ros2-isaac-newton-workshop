#!/usr/bin/env bash
# Full VM preparation, never cloud provisioning or host driver modification.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --accept-nvidia-eula || "${2:-}" != --accept-mesh-license ]]; then
  echo 'Review licenses; use --accept-nvidia-eula --accept-mesh-license.' >&2
  exit 2
fi
command -v uv >/dev/null || { printf '%s\n' 'uv is required for the host notebook kernel; ask staff to prepare it before building images.' >&2; exit 2; }
bash scripts/brev_preflight.sh
mkdir -p .workshop/receipts .workshop/agent-output
# Reuse the signed-package base; build it only if absent. No host apt changes.
base="${ROS_BASE:-roscon/ros5-base:5.0}"
if ! docker image inspect "$base" >/dev/null 2>&1; then
  trap 'docker rm -f roscon-brev-ros-base >/dev/null 2>&1 || true' EXIT
  docker run -d --name roscon-brev-ros-base --memory=24g --cpus=8 \
    -v "$PWD/docker:/bootstrap:ro" \
    ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c sleep infinity
  timeout 2400 docker exec roscon-brev-ros-base bash /bootstrap/install_ros5.sh
  docker cp roscon-brev-ros-base:/opt/workshop-receipts/. .workshop/receipts/
  docker commit roscon-brev-ros-base "$base"
  docker rm -f roscon-brev-ros-base
  trap - EXIT
fi
# Source layers rebuild on changes; repeat setup is Docker-cache and asset-hash safe.
docker build --resource memory=24g --resource cpu-quota=800000 \
  --build-arg "ROS_BASE=$base" -f docker/Dockerfile \
  -t "${WORKSHOP_ROS_IMAGE:-roscon/microduck-ros5:local}" .
docker build --resource memory=8g --resource cpu-quota=400000 \
  --build-arg "ROS_IMAGE=${WORKSHOP_ROS_IMAGE:-roscon/microduck-ros5:local}" \
  --target agent -f docker/sim.Dockerfile -t "${WORKSHOP_AGENT_IMAGE:-roscon/microduck-agent:local}" .
docker run --rm --name roscon-brev-agent-api --memory=4g --cpus=2 \
  "${WORKSHOP_AGENT_IMAGE:-roscon/microduck-agent:local}" python -m microduck_workshop.agent.api_check \
  | tee .workshop/receipts/cascade-api.json
bash scripts/sim_setup.sh "$@"
if [[ ! -f scripts/model_setup.sh ]]; then
  echo 'Missing model setup lane; full deployment is incomplete. Merge scripts/model_setup.sh and docs/local_model.md.' >&2
  exit 2
fi
bash scripts/model_setup.sh
bash scripts/model_setup.sh --verify-only
bash scripts/notebook_setup.sh
printf '%s\n' 'Sim, ROS5, CASCADE, pinned local model and host notebook kernel prepared. No paid cloud resources were created.'
