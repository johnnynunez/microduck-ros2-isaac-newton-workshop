"""CPU-only grading; default reference, explicit CAPSTONE_TOOLS_FILE for students."""

import importlib.util
import os
from pathlib import Path

import pytest
from test_agent_domain import FixtureGateway

from microduck_workshop.agent.domain import MicroduckDomain

ROOT = Path(__file__).parents[1]


@pytest.fixture
def candidate():
    path = Path(os.environ.get("CAPSTONE_TOOLS_FILE", ROOT / "solutions/capstone/tools.py"))
    spec = importlib.util.spec_from_file_location("candidate_tools", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_translation_returns_only_sensor_data(candidate):
    raw = FixtureGateway().observe()
    raw.update(world_pose=[42, 42, 42], lease_token="SECRET", map={"goal": [42, 42]})
    obs = candidate.translate_observation(
        raw, episode_id="episode-1", frame_id="microduck_camera_optical", round_trip_s=0.02
    )
    assert obs["signal"] == "GO" and obs["fresh"] is True
    assert obs["age_s"] == pytest.approx(0.03)
    assert "SECRET" not in str(obs) and "world_pose" not in str(obs) and "map" not in obs


@pytest.mark.parametrize(
    "changes",
    [
        {"tag_ids": []},
        {"tag_ids": [0, 1]},
        {"fresh": False},
        {"age_s": 0.51},
        {"age_s": float("nan")},
        {"age_s": -1},
        {"episode_id": "foreign"},
        {"frame_id": "foreign"},
        {"tag_ids": [True]},
        {"generation": True},
    ],
)
def test_unsafe_observation_never_grants_GO(candidate, changes):
    raw = FixtureGateway().observe()
    raw.update(changes)
    result = candidate.translate_observation(
        raw, episode_id="episode-1", frame_id="microduck_camera_optical"
    )
    assert result.get("signal") != "GO"


def test_motion_uses_fresh_gate_and_real_verdict(candidate):
    gateway = FixtureGateway()
    domain = MicroduckDomain(
        gateway,
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        observation_handler=candidate.translate_observation,
        motion_handler=candidate.step_forward,
    )
    assert domain.execute("observe", {})["signal"] == "GO"
    receipt = candidate.step_forward(domain, {"action": "step_forward"})
    cmd = gateway.sent[0]
    assert (cmd.vx, cmd.vy, cmd.wz, cmd.duration_s) == (.1, 0., 0., 2.)
    assert len(gateway.sent) == 1
    assert receipt["accepted"] is True and receipt["verified"] is False
    assert receipt["postcondition"]["status"] == "refuted"
    assert "SECRET" not in str(receipt)


@pytest.mark.parametrize(
    "changes", [{"vx": True}, {"vx": float("nan")}, {"duration_s": 3}, {"extra": 1}]
)
def test_invalid_motion_is_not_clipped(candidate, changes):
    gateway = FixtureGateway()
    domain = MicroduckDomain(gateway, episode_id="episode-1", frame_id="microduck_camera_optical")
    domain.execute("observe", {})
    args = dict(changes)
    try:
        receipt = candidate.step_forward(domain, args)
    except ValueError:
        receipt = {"ok": False}
    assert receipt["ok"] is False and not gateway.sent
