#!/usr/bin/env bash
# Reference VM setup entrypoint. No cloud provisioning or host apt/driver changes.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/brev_preflight.sh
mkdir -p .workshop/receipts
# On a shared workstation launch this entire script via heavyrun; on Brev
# each Docker workload below still has explicit 24 GiB / 8 CPU limits.
bash scripts/ros_bootstrap_local.sh
bash scripts/ros_build_image.sh
printf '%s\n' 'ROS image built. Follow parent asset/Sim/model preparation before starting. No paid cloud resources were created.'
