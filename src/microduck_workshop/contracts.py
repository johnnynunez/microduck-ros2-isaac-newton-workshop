"""Strict, simulation-only command admission shared by the ROS and Newton owners."""

import math
import re
from dataclasses import asdict, dataclass, fields

MAX_VX = 0.10
MAX_VY = 0.0
MAX_WZ = 0.30
MAX_DURATION_S = 2.0
MIN_DURATION_S = 0.02
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
    try:
        number = float(value)
    except OverflowError as exc:
        raise ContractError(f"{name} must be representable as a finite number") from exc
    if not math.isfinite(number):
        raise ContractError(f"{name} must be finite")
    return number


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
        if type(self.expected_generation) is not int or not 0 <= self.expected_generation < 2**64:
            raise ContractError("expected_generation must be a uint64 integer")
        for name, limit in (("vx", MAX_VX), ("vy", MAX_VY), ("wz", MAX_WZ)):
            value = finite_number(getattr(self, name), name)
            if abs(value) > limit:
                raise ContractError(f"{name} exceeds {limit}; requests are rejected, not clipped")
        duration = finite_number(self.duration_s, "duration_s")
        if not MIN_DURATION_S <= duration <= MAX_DURATION_S:
            raise ContractError(f"duration_s must be in [{MIN_DURATION_S}, {MAX_DURATION_S}]")

    @classmethod
    def from_dict(cls, value: object) -> "MotionCommand":
        names = {field.name for field in fields(cls)}
        if not isinstance(value, dict) or set(value) != names:
            raise ContractError(f"Command requires exactly these fields: {sorted(names)}")
        return cls(**value)

    def as_dict(self) -> dict:
        return asdict(self)
