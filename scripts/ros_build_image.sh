#!/usr/bin/env bash
# Capped, portable equivalent of docker/Dockerfile; no BuildKit daemon escapes.
set -euo pipefail
cd "$(dirname "$0")/.."
name=roscon-ros5-image-build
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --memory=24g --cpus=8 \
  -v "$PWD:/input:ro" roscon/ros5-base:5.0 sleep infinity
docker exec "$name" bash -c '
set -e
mkdir -p /opt/workshop/ros_ws
cp /input/pyproject.toml /input/README.md /input/LICENSE /opt/workshop/
cp -r /input/src /opt/workshop/
cp -r /input/ros_ws/src /opt/workshop/ros_ws/
cp /input/docker/entrypoint.sh /opt/workshop/
python3 -m venv --system-site-packages /opt/workshop/venv
/opt/workshop/venv/bin/pip install --no-deps /opt/workshop
source /opt/ros/lyrical/setup.bash
cd /opt/workshop/ros_ws
colcon build --parallel-workers 2
'
docker commit \
  --change 'ENV PYTHONPATH=/opt/workshop/src LANG=C.UTF-8 LC_ALL=C.UTF-8' \
  --change 'ENV ROS_DOMAIN_ID=27 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST RMW_IMPLEMENTATION=rmw_fastrtps_cpp' \
  --change 'WORKDIR /opt/workshop/ros_ws' \
  --change 'ENTRYPOINT ["/bin/bash", "/opt/workshop/entrypoint.sh"]' \
  --change 'CMD ["ros2", "launch", "microduck_workshop_ros", "workshop.launch.py"]' \
  "$name" "${WORKSHOP_ROS_IMAGE:-roscon/microduck-ros5:local}"
docker image inspect "${WORKSHOP_ROS_IMAGE:-roscon/microduck-ros5:local}" \
  --format '{{json .}}' > .workshop/receipts/runtime-image.json
