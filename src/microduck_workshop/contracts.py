"""Strict, simulation-only command admission shared by the ROS and Newton owners."""

import math
import re
from dataclasses import asdict, dataclass, fields

MAX_VX = 0.10
MAX_VY = 0.0
MAX_WZ = 0.30
MAX_DURATION_S = 2.0
LEASE_TIMEOUT_S = 0.5
MAX_SENSOR_AGE_S = 0.5
PROTOCOL_VERSION = 1


class ContractError(ValueError):
    """The request is malformed, ambiguous, or outside the fixed lesson envelope."""


def identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ContractError(f"{name} must be 1..64 ASCII identifier characters")
    return value


def finite_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a number, not a boolean or string")
    if not math.isfinite(value):
        raise ContractError(f"{name} must be finite")
    return float(value)


@dataclass(frozen=True)
class MotionCommand:
    episode_id: str
    request_id: str
    expected_generation: int
    vx: float
    vy: float
    wz: float
    duration_s: float

    def __post_init__(self) -> None:
        identifier(self.episode_id, "episode_id")
        identifier(self.request_id, "request_id")
        if type(self.expected_generation) is not int or self.expected_generation < 0:
            raise ContractError("expected_generation must be a nonnegative integer")
        for name, limit in (("vx", MAX_VX), ("vy", MAX_VY), ("wz", MAX_WZ)):
            value = finite_number(getattr(self, name), name)
            if abs(value) > limit:
                raise ContractError(f"{name} exceeds {limit}; requests are rejected, not clipped")
        duration = finite_number(self.duration_s, "duration_s")
        if not 0 < duration <= MAX_DURATION_S:
            raise ContractError(f"duration_s must be in (0, {MAX_DURATION_S}]")

    @classmethod
    def from_dict(cls, value: object) -> "MotionCommand":
        names = {field.name for field in fields(cls)}
        if not isinstance(value, dict) or set(value) != names:
            raise ContractError(f"Command requires exactly these fields: {sorted(names)}")
        return cls(**value)

    def as_dict(self) -> dict:
        return asdict(self)
