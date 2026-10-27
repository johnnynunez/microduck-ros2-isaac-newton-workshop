"""Portable evidence consistency, not a substitute for fresh native execution."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_native_step_receipts_match_fixed_preregistration_and_current_sources():
    raw = (ROOT / "provenance/step_preregistration.json").read_bytes()
    plan = json.loads(raw)
    receipt = json.loads((ROOT / "provenance/step_validation.json").read_text())
    assert receipt["preregistration_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["preregistration"] == plan
    cases = receipt["holdouts"]
    assert len(cases) == len(plan["cases"]) == 4
    assert {r["case"]["id"] for r in cases} == {c["id"] for c in plan["cases"]}
    assert receipt["gating_request_count"] == sum(
        len(r["requests"]) for r in cases if r["case"]["gating"]
    )
    assert receipt["confirmation_request_count"] == sum(
        len(r["requests"]) for r in cases if not r["case"]["gating"]
    )
    for case in cases:
        assert case["both_completed_requests_verified"]
        assert not case["renewal_errors"]
        assert all(r["physical_status"]["verified"] for r in case["requests"])
        assert case["proof_expiry"]["reason"] == "observation proof expired"
        assert case["lease_expiry"]["reason"] == "wall lease expired"
        assert case["interrupted"]["status"] == "stopped"
        assert not case["interrupted"]["verified"]
        assert len(case["runtime"]["joint_names"]) == 28
        assert case["runtime"]["model_body_count"] == 15
        assert case["runtime"]["camera_enabled"] is False
    confirmation = next(r for r in cases if not r["case"]["gating"])
    assert not confirmation["runtime"]["step_profile"]["candidate_validation"]
    assert confirmation["runtime"]["step_profile"]["validation_status"] == "NATIVE_VALIDATED"
    # Historical measurements remain bound to their original source hashes.
    # Only these protocol files changed, then passed a separate fresh native
    # fence/restart campaign. Never rewrite the original eight-pass receipt.
    fence = json.loads((ROOT / "provenance/native_fence_validation.json").read_text())
    for path, digest in fence["prior_receipts_preserved"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    revalidated_protocol = {
        "src/microduck_workshop/sim/http.py",
        "src/microduck_workshop/sim/intent.py",
    }
    assert all(r["physical_status"]["verified"] for r in fence["requests"])
    assert fence["runtime"]["camera_enabled"] is False
    for path, digest in plan["code_sha256"].items():
        if path.endswith("policy/step.py"):
            digest = receipt["production_adapter_sha256"]
        elif path in revalidated_protocol:
            digest = fence["source_sha256"][path]
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
    for path, digest in receipt["additional_unchanged_source_sha256"].items():
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest
