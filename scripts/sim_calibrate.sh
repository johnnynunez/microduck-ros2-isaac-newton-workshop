#!/usr/bin/env bash
# Offline neural-command diagnostics only; does not change the public HTTP bounds.
set -u
: "${ISAACLAB_ROOT:?Set ISAACLAB_ROOT}"
: "${MICRODUCK_ASSET_ROOT:?Set MICRODUCK_ASSET_ROOT}"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
for vx in .25 .275 .30 .325; do
    "$ISAACLAB_ROOT/.venv/bin/python" -m microduck_workshop.sim.play \
      --asset-root "$MICRODUCK_ASSET_ROOT" --mode validate --steps 350 \
      --validation-vx "$vx" --output ".workshop/calibration-${vx}" \
      > ".workshop/calibration-${vx}.log" 2>&1
    printf 'neural_vx=%s exit=%s\n' "$vx" "$?"
done
