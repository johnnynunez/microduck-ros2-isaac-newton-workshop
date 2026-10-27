#!/usr/bin/env bash
# Read-only host gate; does not provision instances, install drivers, or touch robots.
set -euo pipefail
command -v docker
command -v nvidia-smi
docker info >/dev/null
docker compose version
python3 - <<'PY'
import shutil, subprocess
rows = subprocess.check_output(['nvidia-smi', '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader,nounits'], text=True).splitlines()
for row in rows:
    name, driver, memory = [v.strip() for v in row.split(',')]
    assert int(driver.split('.')[0]) >= 595, 'Isaac ROS 5 requires driver 595+; select a supported Brev image, do not downgrade ROS'
    assert int(memory) >= 8192, 'GPU needs at least 8 GiB; full workshop requires L40S/RTX PRO budget'
    print(name, driver, memory)
free = shutil.disk_usage('.').free
assert free > 32 * 1024**3, 'Need >32 GiB free for ROS alone; plan >=200 GiB for full workshop'
print('ROS prerequisites passed. This is not a cloud execution or full workshop readiness claim.')
PY
