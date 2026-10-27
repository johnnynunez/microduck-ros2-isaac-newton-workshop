#!/usr/bin/env bash
# Exercise the copied runtime image, not a source bind mount. No simulator fixture.
set -euo pipefail
cd "$(dirname "$0")/.."
name=roscon-ros5-runtime-smoke
out="$PWD/.workshop/receipts"
mkdir -p "$out"
cleanup() {
  docker stop --time 8 "$name" >/dev/null 2>&1 || true
  docker logs "$name" > "$out/runtime-container.log" 2>&1 || true
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker run -d --name "$name" --memory=24g --cpus=8 --shm-size=1g \
  --gpus "device=${WORKSHOP_GPU:-1}" --network host \
  -e ROS_DOMAIN_ID=89 -e ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
  -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  "${WORKSHOP_ROS_IMAGE:-roscon/microduck-ros5:local}" \
  ros2 launch microduck_workshop_ros workshop.launch.py sim_url:=http://127.0.0.1:18766
docker inspect "$name" --format '{{json .HostConfig}}' > "$out/runtime-hostconfig.json"
docker exec "$name" bash /opt/workshop/entrypoint.sh ros2 pkg executables microduck_workshop_ros
# CLI waits for discovery; timeout bounds failed launch rather than hanging.
timeout 20 docker exec "$name" bash /opt/workshop/entrypoint.sh ros2 service call \
  /workshop/microduck/observe microduck_workshop_interfaces/srv/Observe '{}'
timeout 10 docker exec "$name" bash /opt/workshop/entrypoint.sh ros2 param get \
  /workshop/microduck/apriltag backends
timeout 10 docker exec "$name" bash /opt/workshop/entrypoint.sh ros2 param get \
  /workshop/microduck/apriltag tag_family
docker exec "$name" bash -c 'sha256sum --check /opt/workshop-receipts/bootstrap-sha256.txt'
docker exec "$name" bash /opt/workshop/entrypoint.sh python3 -c \
  'import rclpy, sys; from microduck_workshop_interfaces.srv import Observe; print(sys.version); print(rclpy.__file__); print(Observe.Response.get_fields_and_field_types())'
