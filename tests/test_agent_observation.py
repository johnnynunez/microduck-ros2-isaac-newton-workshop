"""CPU contract fixtures only; these are NOT Isaac ROS perception evidence."""

import pytest

from microduck_workshop.agent.observation import translate_observation


def observation(**overrides):
    return dict(
        fresh=True,
        episode_id="episode-1",
        generation=3,
        frame_sequence=20,
        sim_time=1.25,
        age_s=0.1,
        frame_id="microduck_camera_optical",
        tag_ids=[0],
        reason="world_pose=SECRET",
        world_pose=[99, 88, 77],
        lease_token="SECRET",
        **overrides,
    )


def test_observation_is_an_allowlist_not_size_projection():
    result = translate_observation(
        observation(),
        episode_id="episode-1",
        frame_id="microduck_camera_optical",
        round_trip_s=0.05,
    )
    assert result["ok"] is True
    assert result["signal"] == "GO"
    assert result["age_s"] == pytest.approx(0.15)
    assert set(result) == {
        "ok",
        "fresh",
        "episode_id",
        "generation",
        "frame_sequence",
        "sim_time",
        "age_s",
        "frame_id",
        "tag_ids",
        "signal",
        "reason",
    }
    assert "SECRET" not in str(result)
