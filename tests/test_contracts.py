import math

import pytest

from microduck_workshop.contracts import ContractError, MotionCommand


def payload(**changes):
    value = {
        "episode_id": "episode-001",
        "request_id": "request-001",
        "expected_generation": 0,
        "vx": 0.1,
        "vy": 0.0,
        "wz": 0.0,
        "duration_s": 1.0,
    }
    value.update(changes)
    return value


def test_motion_schema_accepts_bounded_exact_payload():
    value = MotionCommand.from_dict(payload())
    assert value.as_dict() == payload()


@pytest.mark.parametrize(
    "changes",
    [
        {"vx": math.nan},
        {"vx": math.inf},
        {"vx": True},
        {"vx": "0.1"},
        {"vx": 0.100001},
        {"vy": 0.01},
        {"wz": -0.300001},
        {"duration_s": 0},
        {"duration_s": 2.00001},
        {"duration_s": False},
        {"expected_generation": True},
        {"expected_generation": -1},
        {"expected_generation": 1.0},
        {"episode_id": "../other"},
        {"request_id": ""},
        {"extra": 1},
    ],
)
def test_motion_schema_refuses_unsafe_or_ambiguous_inputs(changes):
    with pytest.raises(ContractError):
        MotionCommand.from_dict(payload(**changes))


@pytest.mark.parametrize("field", ["vx", "vy", "wz", "duration_s"])
@pytest.mark.parametrize("sign", [-1, 1])
def test_oversized_json_integers_raise_contract_error(field, sign):
    import json

    value = json.loads(json.dumps(payload(**{field: sign * 10**1000})))
    with pytest.raises(ContractError):
        MotionCommand.from_dict(value)


@pytest.mark.parametrize("generation", [2**64, 10**1000])
def test_expected_generation_refuses_uint64_overflow(generation):
    with pytest.raises(ContractError, match="uint64"):
        MotionCommand.from_dict(payload(expected_generation=generation))


def test_expected_generation_accepts_uint64_maximum():
    value = MotionCommand.from_dict(payload(expected_generation=2**64 - 1))
    assert value.expected_generation == 2**64 - 1


def test_motion_schema_requires_every_field():
    value = payload()
    del value["episode_id"]
    with pytest.raises(ContractError):
        MotionCommand.from_dict(value)
