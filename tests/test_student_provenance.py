"""Portable consistency of fresh real evidence; not a substitute for live execution."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
EVIDENCE = ROOT / "provenance/student_policy_v3"
HISTORY = ROOT / "provenance/student_policy"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def test_student_receipts_bind_actual_changed_export_and_current_control_sources():
    training = read(EVIDENCE / "training_receipt.json")
    manifest = read(EVIDENCE / "policy_manifest.json")
    admission = read(EVIDENCE / "admission.json")
    handoff = read(EVIDENCE / "native_handoff.json")
    redactions = read(EVIDENCE / "redactions.json")
    original_training = next(
        f for f in redactions["files"] if f["public_file"] == "training_receipt.json"
    )
    assert manifest["training_receipt"]["sha256"] == original_training["original_sha256"]
    assert original_training["public_sha256"] == digest(EVIDENCE / "training_receipt.json")
    assert manifest["checkpoint"]["sha256"] == training["checkpoint_sha256"]
    assert admission["manifest_sha256"] == digest(EVIDENCE / "policy_manifest.json")
    actual = training["actor_sha256"]
    assert actual != training["parent_policy_sha256"]
    assert {actual} == {
        manifest["actor"]["sha256"],
        admission["policy_sha256"],
        handoff["policy_sha256"],
    }
    assert handoff["selected_policy_identity"]["admission_sha256"] == digest(
        EVIDENCE / "admission.json"
    )
    assert training["actor_changed_parameters"] > 0 and training["saved_optimizer_steps"] == 16
    assert training["physics_steps"] == 512 and len(training["updates"]) == 4
    assert training["full_ppo_resume"] is training["converged_gait"] is False
    assert training["critic_init"] == "fresh_random" and training["optimizer_init"] == "fresh_adam"
    assert training["warmstart_parity"]["samples"] == training["export_parity"]["samples"] == 128
    assert training["warmstart_parity"]["max_abs_error"] < 2e-5
    assert training["export_parity"]["max_abs_error"] < 2e-5
    assert admission["passed"] and len(admission["cases"]) == 4
    assert sum(len(c["verdicts"]) for c in admission["cases"]) == 12
    assert all(v["verified"] for c in admission["cases"] for v in c["verdicts"])
    assert admission["source_sha256"] == manifest["source_sha256"]
    for name, expected in manifest["source_sha256"].items():
        assert digest(ROOT / "src/microduck_workshop" / name) == expected
    for name, expected in training["training_source_sha256"].items():
        assert digest(ROOT / "src/microduck_workshop/sim" / name) == expected
    assert (
        digest(ROOT / "src/microduck_workshop/policy/warmstart.py")
        == training["warmstart_source_sha256"]
    )


def test_student_and_default_live_native_handoff_preserved_expiry_and_stop():
    for path in (
        EVIDENCE / "native_handoff.json",
        EVIDENCE / "canonical_native_handoff.json",
    ):
        result = read(path)
        assert result["scope"] == "native_only_not_ros_agent_acceptance"
        assert result["passed"] and result["server_exit_code"] == 0
        assert len(result["requests"]) == 2
        assert all(r["physical_status"]["verified"] for r in result["requests"])
        assert result["proof_expiry"]["reason"] == "observation proof expired"
        assert result["lease_expiry"]["reason"] == "wall lease expired"
        assert result["interrupted"]["status"] == "stopped"
        assert result["interrupted"]["verification_available"]
        assert not result["interrupted"]["verified"]
        assert not result["renewal_errors"]
        assert result["prior_native_merged_sha256"] == digest(
            ROOT / "provenance/native_merged_validation.json"
        )
        assert result["harness_sha256"] == digest(ROOT / "scripts/policy_handoff_probe.py")
        for name, expected in result["source_sha256"].items():
            assert digest(ROOT / name) == expected
    canonical = read(EVIDENCE / "canonical_native_handoff.json")
    assert (
        canonical["policy_sha256"]
        == "2fc7f8ee6acd7d0d3f66a99927b5d5a56589aeed02ec714de329b252d5ccf492"
    )


def test_incomplete_first_admission_stays_failed_and_immutable():
    first = read(HISTORY / "attempt01_incomplete_admission.json")
    manifest = read(HISTORY / "attempt01_policy_manifest.json")
    assert first["passed"] is False
    assert first["manifest_sha256"] == digest(HISTORY / "attempt01_policy_manifest.json")
    path = HISTORY / "attempt01_training_receipt.json"
    publication = read(ROOT / "provenance/public_redaction_manifest.json")
    entry = next(item for item in publication["files"] if item["path"] == str(path.relative_to(ROOT)))
    assert digest(path) == entry["published_sha256"]
    assert manifest["training_receipt"]["sha256"] == entry["original_sha256"]
    assert first["policy_sha256"] != read(HISTORY / "admission.json")["policy_sha256"]


def test_unsuccessful_http_episode_and_adversarial_rejections_stay_visible():
    failed = read(EVIDENCE / "first_attempt_native_handoff.json")
    assert failed["passed"] is False and "error" in failed
    assert failed["policy_sha256"] == read(EVIDENCE / "native_handoff.json")["policy_sha256"]
    assert failed["requests"][-1]["physical_status"]["verified"] is False
    audit = read(EVIDENCE / "cpu_adversarial_actor_audit.json")
    assert audit["stale_traces_rebound_to_unexecuted_zero_actor"]["selected_for_serve"] is False
    assert (
        "ONNX output/raw action mismatch"
        in audit["stale_traces_rebound_to_unexecuted_zero_actor"]["rejection"]
    )
    probes = read(EVIDENCE / "cpu_identity_admission_rejections.json")
    assert probes["redirect_followed"]["requests"] == ["/v1/health"]
    assert probes["environment_proxy_used"]["requests"] == []
    for key in (
        "redirect_followed",
        "environment_proxy_used",
        "duplicated_first_case_and_wrong_plan",
        "zero_raw_actions_invalid_gravity_and_command_observations",
        "final_receipt_with_teardown_error",
    ):
        assert probes[key]["accepted"] is False
    assert read(EVIDENCE / "cpu_teardown_rejection.json")["receipt_passed_after_exception"] is False


def test_publication_redactions_are_explicit_and_public_hashes_match():
    ledger = read(EVIDENCE / "redactions.json")
    assert ledger["scope"] == "publication_copies_not_deployable_artifacts"
    assert ledger["originals_preserved"] is True
    for entry in ledger["files"]:
        path = EVIDENCE / entry["public_file"]
        assert digest(path) == entry["public_sha256"]
        assert "/home/" not in path.read_text()
        assert (entry["public_sha256"] != entry["original_sha256"]) == bool(
            entry["redacted_json_pointers"]
        )
        data = read(path)
        for pointer in entry["redacted_json_pointers"]:
            value = data
            for key in pointer.split("/")[1:]:
                value = value[int(key)] if isinstance(value, list) else value[key]
            assert value == ledger["replacement"]
