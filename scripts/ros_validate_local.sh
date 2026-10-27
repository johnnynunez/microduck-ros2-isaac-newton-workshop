#!/usr/bin/env bash
# Wrap this command in heavyrun on the shared instructor workstation.
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-all}
name="roscon-ros5-validate-${mode}"
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
mkdir -p .workshop/receipts
docker run --name "$name" --memory=24g --cpus=8 --shm-size=1g \
  --gpus "device=${WORKSHOP_GPU:-1}" --network host \
  -e ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-87}" -e ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
  -e RMW_IMPLEMENTATION=rmw_fastrtps_cpp -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  -e VALIDATE_MODE="$mode" -e WORKSHOP_ROOT=/workshop \
  -v "$PWD:/workshop" -w /workshop roscon/ros5-base:5.0 bash -c '
set -e
source /opt/ros/lyrical/setup.bash
export PYTHONPATH=/workshop/src:/workshop/ros_ws/src/microduck_gateway:$PYTHONPATH
nvidia-smi --query-gpu=index,uuid,name,driver_version --format=csv
python3 --version
if [[ "$VALIDATE_MODE" != apriltag ]]; then
  cd /workshop/ros_ws
  colcon build --parallel-workers 2
  source install/setup.bash
  cd /workshop
  python3 -m pytest tests/test_ros*.py -v
fi
if [[ "$VALIDATE_MODE" != dds ]]; then
  python3 scripts/ros_apriltag_smoke.py
fi
'
