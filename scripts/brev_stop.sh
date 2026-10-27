#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Bounded teardown; no automatic new-episode/re-arm. ACK does not prove rest.
# Include `compose run --rm agent` one-offs, not only a long-lived service container.
mapfile -t agent_ids < <(docker ps -q --filter label=com.docker.compose.project=roscon-brev --filter label=com.docker.compose.service=agent)
if ((${#agent_ids[@]})); then docker stop --time 8 "${agent_ids[@]}"; fi
docker compose --profile agent stop --timeout 8 agent || true
if [[ "$(docker inspect -f '{{.State.Running}}' roscon-brev-ros 2>/dev/null || true)" == true ]]; then
  timeout 8 docker compose exec -T ros bash /opt/workshop/entrypoint.sh \
    ros2 service call /workshop/microduck/emergency_stop std_srvs/srv/Trigger '{}' || true
fi
bash scripts/sim_stop.sh
for name in roscon-brev-train roscon-brev-warmup roscon-brev-assets; do
  if [[ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || true)" == true ]]; then
    docker stop --time 10 "$name"
  fi
done
docker compose --profile agent down --timeout 10
# Model has a separate owner; use only its documented launcher if present.
if [[ -f scripts/model_stop.sh ]]; then bash scripts/model_stop.sh; fi
printf '%s\n' 'Containers stopped. Stop/delete the INSTANCE in the Brev Console and verify state; VM/storage billing may continue.'
