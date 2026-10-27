"""Authored-scene and read-only timing contracts; not physical evidence."""

from types import SimpleNamespace

import numpy as np
import pytest

from microduck_workshop.sim import camera


def test_static_signal_board_is_centered_lower_and_farther_with_same_size():
    points = np.asarray(camera.teaching_signal_vertices())
    assert points.shape == (4, 3)
    np.testing.assert_allclose(points.mean(axis=0), (1.0, 0.0, 0.16))
    np.testing.assert_allclose(np.ptp(points, axis=0), (0.0, 0.25, 0.25))


def test_observer_wait_uses_existing_cap_without_extending_motion():
    from microduck_workshop.agent.domain import MicroduckDomain

    domain = MicroduckDomain(SimpleNamespace(synthetic=True), episode_id="ep", frame_id="head")
    assert domain.verification_timeout_s == 8.0
    with pytest.raises(ValueError, match="verification budget"):
        MicroduckDomain(
            SimpleNamespace(synthetic=True),
            episode_id="ep",
            frame_id="head",
            verification_timeout_s=8.01,
        )
