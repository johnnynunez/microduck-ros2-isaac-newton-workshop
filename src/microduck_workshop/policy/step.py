"""Fixed planned step, distinct from every constant-velocity command profile.

Only elapsed simulation time chooses the phase. No world-truth feedback.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from microduck_workshop.contracts import ContractError

from .calibration import SOURCE_REVISION
from .contract import POLICY_SHA256

STEP_NAME = "step-forward-v1"
VALIDATION_STATUS = "NATIVE_VALIDATED"


@dataclass(frozen=True)
class StepProfile:
    candidate_validation: bool = False
    name: str = STEP_NAME

    def bind(self, *, policy_sha256, policy_mode):
        if policy_sha256 != POLICY_SHA256 or policy_mode != "training":
            raise ValueError("step requires pinned public v8 and unfiltered training action mode")

    def validate_request(self, command):
        if not self.candidate_validation and VALIDATION_STATUS != "NATIVE_VALIDATED":
            raise ContractError("step-forward-v1 NOT_READY: native validation pending or failed")
        if (command.vx, command.vy, command.wz, command.duration_s) != (0.1, 0, 0, 2.0):
            raise ContractError("step-forward-v1 requires fixed peak .1/0/0 and horizon 2.0s")

    def phase(self, elapsed):
        # Grid tolerance only: avoids an extra physics tick from binary roundoff.
        if elapsed < 1.0 - 1e-9:
            return "drive"
        return "settle" if elapsed < 2.0 - 1e-9 else "complete"

    def condition(self, desired):
        if tuple(desired) == (0.1, 0, 0):
            return (0.25, 0.0, 0.0)
        if tuple(desired) == (0, 0, 0):
            return (0.0, 0.0, 0.0)
        raise ContractError("unsupported planned-step phase command")

    def receipt(self):
        spec = {
            "name": self.name,
            "source_revision": SOURCE_REVISION,
            "policy_sha256": POLICY_SHA256,
            "adapter_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "requested_peak": [0.1, 0.0, 0.0],
            "drive_s": 1.0,
            "settle_s": 1.0,
            "horizon_s": 2.0,
            "drive_neural_command": [0.25, 0.0, 0.0],
            "settle_neural_command": [0.0, 0.0, 0.0],
            "validation_status": VALIDATION_STATUS,
            "candidate_validation": self.candidate_validation,
            "online_feedback": False,
            "production_requires_observation_proof": True,
        }
        spec["profile_sha256"] = hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return spec
