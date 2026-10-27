"""Explicit offline command conditioning; never consumes simulator truth."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from microduck_workshop.contracts import ContractError

from .contract import POLICY_SHA256

SOURCE_REVISION = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
PROFILE_NAME = "calibrated-forward-v1"
ADAPTER_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class CommandProfile:
    name: str = "direct"

    def __post_init__(self):
        if self.name not in ("direct", PROFILE_NAME):
            raise ValueError("unknown explicit command profile")

    def bind(self, *, policy_sha256, policy_mode):
        if self.name != "direct" and (policy_sha256 != POLICY_SHA256 or policy_mode != "training"):
            raise ValueError(
                "calibration requires pinned public v8 and unfiltered training action mode"
            )

    def validate_request(self, command):
        if self.name == "direct":
            return
        self.condition((command.vx, command.vy, command.wz))
        if command.vx != 0:
            raise ContractError(
                "calibrated-forward-v1 NOT_READY: no forward duration passed frozen rest gates"
            )

    def condition(self, desired):
        desired = tuple(desired)
        if self.name == "direct" or desired == (0, 0, 0):
            return desired
        if self.name == PROFILE_NAME and desired == (0.1, 0, 0):
            return (0.25, 0.0, 0.0)
        raise ContractError("unsupported calibrated desired command; no clipping or extrapolation")

    def receipt(self):
        spec: dict = {
            "name": self.name,
            "source_revision": SOURCE_REVISION,
            "policy_sha256": POLICY_SHA256,
            "adapter_source_sha256": ADAPTER_SOURCE_SHA256,
        }
        if self.name != "direct":
            spec.update(
                desired_points=[[0, 0, 0], [0.1, 0, 0]],
                neural_points=[[0, 0, 0], [0.25, 0, 0]],
                forward_durations_s=[],
                evaluated_candidate_durations_s=[1.0, 2.0],
                validation_status="NOT_READY",
                validation_reason="round1: all HTTP walk/resume requests failed original rest gates",
                neural_training_bounds=[[-0.4, 0.4], [-0.3, 0.3], [-1, 1]],
                policy_mode="training",
                online_feedback=False,
            )
        spec["profile_sha256"] = hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return spec
