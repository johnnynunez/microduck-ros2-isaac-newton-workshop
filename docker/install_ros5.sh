#!/usr/bin/env bash
# Runs INSIDE Ubuntu 24.04 only; never installs host drivers.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
[[ "$VERSION_ID" == 24.04 && "$(dpkg --print-architecture)" == amd64 ]]
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg locales
install -d /usr/share/keyrings /etc/apt/sources.list.d
curl --connect-timeout 15 --max-time 120 --fail --show-error --location https://isaac.download.nvidia.com/isaac-ros/repos.key -o /root/isaac-repos.key
printf '%s\n' 'd45fbd909e89914960a66dba17d4c659adf908ab4d6fe2cf55381e9ffe5ce59d  /root/isaac-repos.key' | sha256sum --check
gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-isaac-ros.gpg /root/isaac-repos.key
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/nvidia-isaac-ros.gpg] https://isaac.download.nvidia.com/isaac-ros/release-5.0 noble main' > /etc/apt/sources.list.d/nvidia-isaac-ros.list
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/nvidia-isaac-ros.gpg] https://isaac.download.nvidia.com/isaac-ros/ubuntu/main noble main' > /etc/apt/sources.list.d/nvidia-isaac-ros-buildfarm.list
curl --connect-timeout 15 --max-time 120 -fSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb -o /root/cuda-keyring.deb
printf '%s\n' 'd2a6b11c096396d868758b86dab1823b25e14d70333f1dfa74da5ddaf6a06dba  /root/cuda-keyring.deb' | sha256sum --check
dpkg -i /root/cuda-keyring.deb
curl --connect-timeout 15 --max-time 120 -fSL https://repo.download.nvidia.com/jetson/jetson-ota-public.asc -o /root/jetson.key
printf '%s\n' '576f852981855e5c6cfb9b625ffb51b984ca451f1181b2e70435b005034fad55  /root/jetson.key' | sha256sum --check
gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-jetson.gpg /root/jetson.key
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/nvidia-jetson.gpg] https://repo.download.nvidia.com/jetson/x86_64/noble r39.2 main' > /etc/apt/sources.list.d/nvidia-jetson.list
curl --connect-timeout 15 --max-time 120 -fSL https://github.com/ros-infrastructure/ros-apt-source/releases/download/1.2.0/ros2-apt-source_1.2.0.noble_all.deb -o /root/ros2-apt-source.deb
printf '%s\n' '0804d9b13db770eb87019be414cd78378835228ad5fa801fc88758596dd8f7e5  /root/ros2-apt-source.deb' | sha256sum --check
dpkg -i /root/ros2-apt-source.deb
apt-get update
apt-cache policy ros-lyrical-ros-base ros-lyrical-isaac-ros-apriltag
apt-get install -y --no-install-recommends ros-lyrical-ros-base ros-lyrical-isaac-ros-apriltag ros-lyrical-rosbag2-storage-mcap ros-lyrical-rosbag2-storage-sqlite3 ros-lyrical-cv-bridge python3-colcon-common-extensions python3-pytest python3-pil python3-venv python3-pip build-essential cmake
mkdir -p /opt/workshop-receipts
dpkg-query -W -f='${Package}\t${Version}\n' > /opt/workshop-receipts/dpkg-lock.tsv
sha256sum /root/isaac-repos.key /root/cuda-keyring.deb /root/jetson.key /root/ros2-apt-source.deb > /opt/workshop-receipts/bootstrap-sha256.txt
rm -rf /var/lib/apt/lists/*
