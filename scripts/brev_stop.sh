#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Best-effort local stop; container removal also ends renewals (0.5 s wall lease).
timeout 8 docker compose exec -T ros bash /opt/workshop/entrypoint.sh ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}' || true
docker compose down --timeout 10
printf '%s
' 'Containers stopped. Brev VM/storage billing may continue: stop/delete the INSTANCE in the Brev Console and verify its state.'
