"""CPU orchestration tests. Fixture bytes are NOT trained policies or live evidence."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks"))


def module():
    assert (ROOT / "notebooks/policy_workshop.py").is_file(), "Missing exact-policy notebook helper"
    return importlib.import_module("policy_workshop")


def test_training_handoff_binds_changed_actor_checkpoint_receipt_and_source(tmp_path):
    m = module()
    run = tmp_path / "fixture-not-real-training"
    run.mkdir()
    for name in ("actor.onnx", "checkpoint.pt", "transitions.jsonl"):
        (run / name).write_text("unit fixture: " + name)
    receipt = {
        "evidence_kind": "LIVE_MICRODUCK_NEWTON_PPO", "actor_init": "public_v8_actor_only",
        "critic_init": "fresh_random", "optimizer_init": "fresh_adam", "full_ppo_resume": False,
        "converged_gait": False, "actor_changed_parameters": 1, "saved_optimizer_steps": 1,
        "physics_steps": 1, "updates": [{"reward_mean": 0.1}],
        "actor_sha256": m.sha256(run / "actor.onnx"),
        "checkpoint_sha256": m.sha256(run / "checkpoint.pt"),
        "transitions": {"path": "transitions.jsonl", "sha256": m.sha256(run / "transitions.jsonl")},
        "training_source_sha256": {n: m.sha256(ROOT / "src/microduck_workshop/sim" / n) for n in ("train.py", "ppo.py")},
        "warmstart_source_sha256": m.sha256(ROOT / "src/microduck_workshop/policy/warmstart.py"),
    }
    (run / "training_receipt.json").write_text(json.dumps(receipt))
    manifest = {
        "schema_version": 1, "kind": "student_actor", "policy_mode": "training",
        "parent_policy_sha256": m.literal(ROOT / "src/microduck_workshop/policy/contract.py", "POLICY_SHA256"),
        "input": {"name": "obs", "shape": [1, 61]}, "output": {"name": "actions", "shape": [1, 14]},
        "source_sha256": m.control_sources(ROOT),
        **{key: {"path": name, "sha256": m.sha256(run / name)} for key, name in
           (("actor", "actor.onnx"), ("checkpoint", "checkpoint.pt"), ("training_receipt", "training_receipt.json"))},
    }
    (run / "policy_manifest.json").write_text(json.dumps(manifest))
    bundle = m.training_bundle(ROOT, run)
    assert bundle["identity"]["checkpoint_sha256"] == receipt["checkpoint_sha256"]
    assert bundle["identity"]["policy_sha256"] == receipt["actor_sha256"]
    assert bundle["identity"]["manifest_sha256"] == m.sha256(run / "policy_manifest.json")
    (run / "checkpoint.pt").write_text("tampered")
    with pytest.raises(ValueError, match="hash"):
        m.training_bundle(ROOT, run)


def test_artifact_path_rejects_traversal_symlink_and_missing(tmp_path):
    m = module()
    outside = tmp_path / "outside"
    outside.write_text("x")
    run = tmp_path / "run"
    run.mkdir()
    for name in ("../outside", "/outside", "missing", "link"):
        if name == "link":
            (run / name).symlink_to(outside)
        with pytest.raises((ValueError, FileNotFoundError)):
            m.checked_file(run, {"path": name, "sha256": hashlib.sha256(b"x").hexdigest()})


def test_live_identity_rejects_wrong_policy_episode_and_runtime():
    m = module()
    identity = {"policy_sha256": "actor", "manifest_sha256": "manifest", "admission_sha256": "admission"}
    health = {"ready": True, "physics": "newton", "episode_id": "fresh",
              "runtime": {"isaacsim": "6.2.0.0", "newton": "1.6.1",
                          "isaaclab_git_sha": "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4",
                          "policy_sha256": "actor", "policy_manifest_sha256": "manifest",
                          "step_profile": {"name": "step-forward-v1", "policy_sha256": "actor",
                                           "admission_sha256": "admission", "validation_status": "NATIVE_VALIDATED"}}}
    assert m.check_identity(health, identity, episode="fresh")["episode_id"] == "fresh"
    for key, value in (("policy_sha256", "pretrained"), ("isaacsim", "wrong")):
        altered = json.loads(json.dumps(health))
        altered["runtime"][key] = value
        with pytest.raises(ValueError, match="identity"):
            m.check_identity(altered, identity, episode="fresh")
    with pytest.raises(ValueError, match="identity"):
        m.check_identity(health, identity, episode="old")
    with pytest.raises(ValueError, match="fresh"):
        m.check_identity(health, identity, previous_episode="fresh")


def test_bundle_mounts_whole_directories_read_only(tmp_path):
    s = module().PolicySession(ROOT, work=tmp_path)
    bundle = {"run": "/a/run", "admission": "/b/admission"}
    mounts = s.bundle_options(bundle)
    assert "/a/run:/policy-run:ro" in mounts
    assert "/b/admission:/policy-admission:ro" in mounts
    assert not any("admission.json:" in arg for arg in mounts)


def test_one_attempt_marked_before_dispatch_and_never_retried(tmp_path):
    s = module().PolicySession(ROOT, work=tmp_path)
    s.claim_attempt("fixture-episode")
    with pytest.raises(RuntimeError, match="attempt"):
        s.claim_attempt("fixture-episode")
    assert module().PolicySession(ROOT, work=tmp_path).state()["attempts"] == ["fixture-episode"]


def test_failed_or_timed_out_job_is_cleaned_without_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace
    s = module().PolicySession(ROOT, work=tmp_path)
    calls = []
    monkeypatch.setattr(s, "start", lambda *a, **kw: calls.append("start"))
    monkeypatch.setattr(s, "stop", lambda *a: calls.append("stop"))
    monkeypatch.setattr(s, "run", lambda *a, **kw: SimpleNamespace(stdout="2\n", returncode=0))
    with pytest.raises(RuntimeError, match="exit 2"):
        s.job("train", "fixture:image", ["fixture"], timeout=10)
    assert calls == ["start", "stop"]
    calls.clear()
    def timeout(*args, **kwargs):
        raise RuntimeError("Deadline exceeded")
    monkeypatch.setattr(s, "run", timeout)
    with pytest.raises(RuntimeError, match="Deadline"):
        s.job("train", "fixture:image", ["fixture"], timeout=10)
    assert calls == ["start", "stop"]


def test_course_mounts_exclude_private_state_assets_and_tokens(tmp_path):
    s = module().PolicySession(ROOT, work=tmp_path)
    options = s.course_options()
    assert f"{ROOT}:/course:ro" not in options
    for directory in ("scripts", "tests", "exercises", "solutions"):
        assert f"{ROOT / directory}:/course/{directory}:ro" in options


def test_capabilities_checks_shipped_help_and_refuses_old_image(tmp_path, monkeypatch):
    s = module().PolicySession(ROOT, work=tmp_path)
    calls = []
    def old_job(*args, **kwargs):
        calls.append((args, kwargs))
        return 0, "usage: old train --asset-root --output --updates --horizon"
    monkeypatch.setattr(s, "job", old_job)
    with pytest.raises(RuntimeError, match="lacks student-policy API"):
        s.capabilities("fixture:old")
    assert len(calls) == 1
    assert "options" not in calls[0][1], "An overlay must not conceal an obsolete shipped image"


def test_canonical_verifier_recomputes_admission_inside_image(tmp_path, monkeypatch):
    s = module().PolicySession(ROOT, work=tmp_path)
    calls = []
    monkeypatch.setattr(s, "job", lambda *args, **kwargs: calls.append((args, kwargs)))
    s.verify_bundle("fixture:image", {"run": "/fixture/run", "admission": "/fixture/admit"})
    args, kwargs = calls[0]
    assert "load_admission('/policy-admission/admission.json',m)" in args[2][1]
    assert "/fixture/admit:/policy-admission:ro" in kwargs["options"]
    assert "--gpus" not in kwargs["options"]


def test_failed_admission_never_selects_pretrained(tmp_path, monkeypatch):
    m = module()
    bundle = {"run": "fixture", "identity": {"policy_sha256": "p", "manifest_sha256": "m"},
              "policy_mode": "training", "files": []}
    monkeypatch.setattr(m, "training_bundle", lambda *args: bundle)
    directory = tmp_path / "admission"
    directory.mkdir()
    (directory / "admission.json").write_text(json.dumps({"passed": False}))
    with pytest.raises(ValueError, match="no agent motion"):
        m.admitted_bundle(ROOT, "fixture", directory)


def test_start_policy_uses_exact_flags_new_episode_and_complete_bundles(tmp_path, monkeypatch):
    m = module()
    s = m.PolicySession(ROOT, work=tmp_path)
    events = []
    monkeypatch.setattr(s, "verify_bundle", lambda *args: events.append("canonical"))
    monkeypatch.setattr(s, "port_available", lambda *args: events.append("port"))
    monkeypatch.setattr(s, "sim_options", lambda *args: [])
    monkeypatch.setattr(s, "start", lambda *args, **kwargs: events.append((args, kwargs)))
    def wait_sim(*args, **kwargs):
        assert "timeout" not in kwargs, "Policy episodes must use the common configurable cold-start budget"
        return {"fixture": "no real simulator"}
    monkeypatch.setattr(s, "wait_sim", wait_sim)
    monkeypatch.setattr(m, "check_identity", lambda h, i, **kw: {"episode_id": "new-fixture"})
    bundle = {"run": "/fixture/run", "admission": "/fixture/admission", "policy_mode": "training", "identity": {}}
    result = s.start_policy("fixture:image", bundle, gpu="0", assets="/fixture/assets", url="http://127.0.0.1:8766", previous_episode="old-fixture")
    assert events[:2] == ["canonical", "port"]
    command = events[2][0][2]
    for flag, value in (("--policy-manifest", "/policy-run/policy_manifest.json"),
                        ("--policy-admission", "/policy-admission/admission.json"),
                        ("--step-profile", "step-forward-v1"), ("--steps", "0")):
        assert command[command.index(flag) + 1] == value
    assert "/fixture/run:/policy-run:ro" in events[2][1]["options"]
    assert result["episode_id"] == "new-fixture"


def test_json_receipts_reject_overflow_nonfinite_numbers(tmp_path):
    path = tmp_path / "receipt.json"
    for value in ("NaN", "Infinity", "1e999"):
        path.write_text('{"metric": ' + value + '}')
        with pytest.raises(ValueError, match="nonfinite"):
            module().read_json(path)


@pytest.mark.skipif(os.environ.get("RUN_NOTEBOOK_POLICY_CPU") != "1", reason="Real Docker policy image opt-in")
def test_actual_prepared_images_have_policy_cli_and_dependencies(tmp_path, monkeypatch):
    monkeypatch.setenv("WORKSHOP_NOTEBOOK_PREFIX", "roscon-nb-complete")
    monkeypatch.setenv("WORKSHOP_ROS_DOMAIN", "72")
    s = module().PolicySession(ROOT, work=tmp_path)
    s.capabilities(os.environ.get("WORKSHOP_SIM_IMAGE", "roscon/microduck-sim:local"))
    s.capabilities(os.environ.get("WORKSHOP_AGENT_IMAGE", "roscon/microduck-agent:local"), agent=True)
    assert not s.state().get("containers")


def test_post_attempt_identity_does_not_read_an_unowned_listener(tmp_path, monkeypatch):
    s = module().PolicySession(ROOT, work=tmp_path)
    reads = []
    monkeypatch.setattr(s, "get_json", lambda url: reads.append(url))
    with pytest.raises(RuntimeError, match="No owned"):
        s.live_identity("http://127.0.0.1:8766", {"identity": {}}, "old", require_unstopped=False)
    assert reads == []
