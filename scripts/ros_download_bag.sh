#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .workshop/apriltag
curl --fail --location --show-error --max-time 900 'https://api.ngc.nvidia.com/v2/resources/nvidia/isaac/isaac_ros_apriltag_assets/versions/5.0.0/files/quickstart.tar.gz' -o .workshop/apriltag/quickstart.tar.gz
printf '%s\n' 'cadc33601d769ef63a792577105d2cee4f1759b0583f5bf9627275812ae77885  .workshop/apriltag/quickstart.tar.gz' | sha256sum --check
sha256sum .workshop/apriltag/quickstart.tar.gz | tee .workshop/receipts/apriltag-bag-sha256.txt
tar -xzf .workshop/apriltag/quickstart.tar.gz -C .workshop/apriltag
