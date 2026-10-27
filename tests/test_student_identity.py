"""Provider receipts must identify the same admitted native policy and episode."""

import pytest


def test_health_identity_requires_exact_episode_policy_manifest_and_admission():
    from microduck_workshop.policy.identity import verify_policy_health

    expected = {
        "policy_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "admission_sha256": "c" * 64,
    }
    health = {
        "ready": True,
        "episode_id": "ep",
        "physics": "newton",
        "runtime": {
            "policy_sha256": "a" * 64,
            "policy_manifest_sha256": "b" * 64,
            "step_profile": {
                "admission_sha256": "c" * 64,
                "policy_sha256": "a" * 64,
                "validation_status": "NATIVE_VALIDATED",
            },
        },
    }
    assert verify_policy_health(health, expected, episode_id="ep")["policy_sha256"] == "a" * 64
    for key in ("policy_sha256", "policy_manifest_sha256"):
        broken = dict(health, runtime=dict(health["runtime"], **{key: "d" * 64}))
        with pytest.raises(ValueError):
            verify_policy_health(broken, expected, episode_id="ep")
    with pytest.raises(ValueError):
        verify_policy_health(health, expected, episode_id="other")
    with pytest.raises(ValueError):
        verify_policy_health(dict(health, ready=False), expected, episode_id="ep")
    with pytest.raises(ValueError):
        verify_policy_health(dict(health, runtime={}), expected, episode_id="ep")
