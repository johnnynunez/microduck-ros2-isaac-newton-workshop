#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .workshop/receipts
name=roscon-ros5-bootstrap
trap 'docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
docker run -d --name "$name" --memory=24g --cpus=8 -v "$PWD/docker:/bootstrap:ro" ubuntu:24.04@sha256:24737cef17f4e22b1977df7d9a05e77c4e28b7da5b8911f8d8ccda136bf3573c sleep infinity
timeout 2400 docker exec "$name" bash /bootstrap/install_ros5.sh
docker cp "$name":/opt/workshop-receipts/. .workshop/receipts/
docker commit "$name" roscon/ros5-base:5.0
