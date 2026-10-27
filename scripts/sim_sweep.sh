#!/usr/bin/env bash
# Diagnostic-only A/B; never changes the frozen ROS/HTTP command envelope.
set -u
: "${ISAACLAB_ROOT:?Set ISAACLAB_ROOT to the clean v3.0.0 checkout}"
: "${MICRODUCK_ASSET_ROOT:?Set MICRODUCK_ASSET_ROOT to fetched public assets}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
for setting in 'training .10' 'training .20' 'deployment .10'; do
    read -r mode vx <<< "$setting"
    "$ISAACLAB_ROOT/.venv/bin/python" -m microduck_workshop.sim.play \
        --asset-root "$MICRODUCK_ASSET_ROOT" --mode validate --steps 350 \
        --policy-mode "$mode" --validation-vx "$vx" \
        --output ".workshop/sweep-${mode}-${vx}" > ".workshop/sweep-${mode}-${vx}.log" 2>&1
    rc=$?
    printf 'mode=%s vx=%s exit=%s\n' "$mode" "$vx" "$rc"
done
