"""CPU protocol/attribution fixtures, not physical acceptance evidence."""

import hashlib
import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from microduck_workshop.contracts import ContractError, MotionCommand
from microduck_workshop.policy.step import StepProfile
from microduck_workshop.sim.evaluate import MotionVerifier
from microduck_workshop.sim.http import SnapshotStore, serve
from microduck_workshop.sim.intent import IntentOwner, ObservationProof


def _submit(owner, token, request_id, kind):
    command = MotionCommand("ep", request_id, owner.generation, 0.1, 0, 0, 2.0)
    if kind == "step":
        return owner.submit_step(command, token, ObservationProof("ep", 1, 0.4))
    return owner.submit(command, token)


@pytest.mark.parametrize("first_kind", ["step", "legacy"])
@pytest.mark.parametrize("next_kind", ["step", "legacy"])
def test_verifier_tail_fences_all_actuation_then_allows_resume(first_kind, next_kind):
    # Hold wall time fixed; exercise the real simulator-time verifier lifecycle.
    owner = IntentOwner("ep", clock=lambda: 0.0, step_profile=StepProfile())
    token = owner.claim("fixture")["lease_token"]
    output = io.StringIO()
    verifier = MotionVerifier(owner, output)
    _submit(owner, token, "first", first_kind)
    for tick in range(119):
        sim_time = tick * 0.02
        truth = {
            "root_pose": [min(0.049, sim_time * 0.049), 0, 0.12, 0, 0, 0, 1],
            "root_velocity": [0.049 if tick < 50 else 0, 0, 0, 0, 0, 0],
        }
        verifier.begin_tick(sim_time, truth)
        owner.consume(sim_time=sim_time)
        verifier.end_tick(sim_time, truth)
        if tick == 100:
            status = owner.status("first")
            assert status["completed"] and not status["verification_available"]
        if 100 <= tick < 118:
            generation = owner.generation
            with pytest.raises(ContractError, match="verification"):
                _submit(owner, token, "unrelated", next_kind)
            assert owner.generation == generation
            assert not owner.status("unrelated")["known"]
            assert owner.consume(sim_time=sim_time) == (0.0, 0.0, 0.0)
    status = owner.status("first")
    assert status["verification_available"] and not status["verified"]
    # The unchanged verifier still rejects the original under-threshold trajectory.
    verdict = json.loads(output.getvalue())
    assert verdict["metrics"]["forward_displacement_m"] == pytest.approx(0.049)
    assert not verdict["verified"]
    assert _submit(owner, token, "resume", next_kind)["accepted"]
    assert owner.consume(sim_time=2.38) == (0.1, 0.0, 0.0)


def test_owner_reclaim_cannot_bypass_unfinished_verification():
    now = [0.0]
    owner = IntentOwner("ep", clock=lambda: now[0])
    token = owner.claim("first-owner")["lease_token"]
    _submit(owner, token, "first", "legacy")
    owner.consume(sim_time=0.0)
    now[0] = 0.51
    assert owner.consume(sim_time=0.1) == (0.0, 0.0, 0.0)
    assert owner.status("first")["status"] == "expired"
    replacement = owner.claim("next-owner")["lease_token"]
    with pytest.raises(ContractError, match="verification"):
        _submit(owner, replacement, "unrelated", "legacy")
    owner.verdict("first", verified=False, reason="interrupted fixture")
    assert _submit(owner, replacement, "resume", "legacy")["accepted"]


def test_priority_stop_remains_available_during_verification():
    owner = IntentOwner("ep", clock=lambda: 0.0)
    token = owner.claim("fixture")["lease_token"]
    _submit(owner, token, "first", "legacy")
    owner.consume(sim_time=0.0)
    owner.consume(sim_time=2.0)
    assert owner.stop("ep", latch=True)["stop_latched"]
    owner.verdict("first", verified=True, reason="fixture only")
    with pytest.raises(ContractError, match="latched"):
        owner.claim("next-owner")
    assert owner.consume(sim_time=2.4) == (0.0, 0.0, 0.0)


PROOF_HEADERS = {
    "X-Workshop-Observation-Episode": "ep",
    "X-Workshop-Observation-Sequence": "2",
    "X-Workshop-Observation-Deadline": "0.45",
}
MALFORMED_PROOFS = [
    pytest.param({}, id="missing"),
    pytest.param({"X-Workshop-Observation-Episode": "ep"}, id="partial"),
    pytest.param(dict(PROOF_HEADERS, **{"X-Workshop-Observation-Sequence": "-1"}), id="negative"),
    pytest.param(dict(PROOF_HEADERS, **{"X-Workshop-Observation-Sequence": "1.0"}), id="decimal"),
    pytest.param(dict(PROOF_HEADERS, **{"X-Workshop-Observation-Sequence": "9" * 5000}), id="huge"),
    pytest.param(dict(PROOF_HEADERS, **{"X-Workshop-Observation-Deadline": "garbage"}), id="text"),
    pytest.param(dict(PROOF_HEADERS, **{"X-Workshop-Observation-Deadline": "nan"}), id="nan"),
]


def _post(server, path, body, token, headers):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}" + path,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            **({"X-Workshop-Lease": token} if token else {}),
            **headers,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


@pytest.mark.parametrize("headers", MALFORMED_PROOFS)
@pytest.mark.parametrize("started", [False, True], ids=["queued", "executing"])
def test_malformed_authenticated_renewal_revokes_step(headers, started):
    owner = IntentOwner("ep", clock=lambda: 0.0, step_profile=StepProfile())
    token = owner.claim("fixture")["lease_token"]
    _submit(owner, token, "step", "step")
    if started:
        assert owner.consume(sim_time=0.0) == (0.1, 0.0, 0.0)
    with serve(SnapshotStore(owner, runtime={"evidence_kind": "CPU_FIXTURE"}), port=0) as server:
        assert _post(server, "/v1/renew", {"episode_id": "ep"}, token, headers)[0] == 409
        assert owner.consume(sim_time=0.005) == (0.0, 0.0, 0.0)
        assert owner.status("step")["status"] == "expired"
        assert _post(server, "/v1/renew", {"episode_id": "ep"}, token, PROOF_HEADERS)[0] == 409
        assert not owner.stop_latched


@pytest.mark.parametrize("headers", MALFORMED_PROOFS)
@pytest.mark.parametrize("identity", ["missing_token", "wrong_token", "wrong_episode"])
def test_unauthenticated_malformed_renewal_cannot_revoke_step(headers, identity):
    owner = IntentOwner("ep", clock=lambda: 0.0, step_profile=StepProfile())
    token = owner.claim("fixture")["lease_token"]
    _submit(owner, token, "step", "step")
    assert owner.consume(sim_time=0.0) == (0.1, 0.0, 0.0)
    supplied = (
        None if identity == "missing_token" else "wrong" if identity == "wrong_token" else token
    )
    episode = "other" if identity == "wrong_episode" else "ep"
    with serve(SnapshotStore(owner, runtime={"evidence_kind": "CPU_FIXTURE"}), port=0) as server:
        assert _post(server, "/v1/renew", {"episode_id": episode}, supplied, headers)[0] == 409
        assert owner.consume(sim_time=0.005) == (0.1, 0.0, 0.0)
        assert owner.status("step")["status"] == "executing"
        assert _post(server, "/v1/renew", {"episode_id": "ep"}, token, PROOF_HEADERS)[0] == 200


def test_malformed_renewal_does_not_extend_or_revoke_legacy_lease():
    now = [0.0]
    owner = IntentOwner("ep", clock=lambda: now[0])
    token = owner.claim("fixture")["lease_token"]
    _submit(owner, token, "legacy", "legacy")
    owner.consume(sim_time=0.0)
    now[0] = 0.2
    with serve(SnapshotStore(owner, runtime={"evidence_kind": "CPU_FIXTURE"}), port=0) as server:
        headers = {"X-Workshop-Observation-Episode": "ep"}
        assert _post(server, "/v1/renew", {"episode_id": "ep"}, token, headers)[0] == 409
        assert owner.consume(sim_time=0.2) == (0.1, 0.0, 0.0)
        now[0] = 0.51
        assert owner.consume(sim_time=0.3) == (0.0, 0.0, 0.0)
        assert owner.status("legacy")["reason"] == "wall lease expired"


def test_native_fence_receipt_binds_protocol_sources_without_rewriting_old_evidence():
    root = Path(__file__).parents[1]
    receipt_path = root / "provenance/native_fence_validation.json"
    assert receipt_path.is_file(), "fresh native fence receipt is missing"
    receipt = json.loads(receipt_path.read_text())
    assert receipt["evidence_kind"] == (
        "FRESH_NATIVE_OPERATOR_PROTOCOL_FENCE_REVALIDATION_NOT_ROS_PERCEPTION"
    )
    for path, digest in receipt["source_sha256"].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
    for path, digest in receipt["prior_receipts_preserved"].items():
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == digest
    assert receipt["source_sha256"]["src/microduck_workshop/sim/evaluate.py"] == (
        "04d83c178af0465ad57d7551e32e0ec292f42bdcbb0ef645d4cf0ed94c83c037"
    )
    assert len(receipt["requests"]) == 2
    assert {r["request_id"] for r in receipt["requests"]} == {"step", "resume"}
    assert all(r["physical_status"]["verified"] for r in receipt["requests"])
    assert all(r["unauthenticated_renewal_http_code"] == 409 for r in receipt["requests"])
    rejections = receipt["tail_fence_rejections"]
    assert len(rejections) == 4
    assert {(r["after"], r["endpoint"]) for r in rejections} == {
        (name, path) for name in ("step", "resume") for path in ("/v1/command", "/v1/step")
    }
    assert all(r["http_code"] == 409 and not r["receipt"]["accepted"] for r in rejections)
    malformed = receipt["authenticated_malformed_renewal"]
    assert malformed["http_code"] == malformed["later_valid_renewal_http_code"] == 409
    assert malformed["cancelled"]["status"] == "expired"
    assert malformed["physical_status"]["verification_available"]
    assert not malformed["physical_status"]["verified"]
    assert malformed["zero_neural_rows_after_cancellation"] > 0
    assert not receipt["renewal_errors"]
    assert receipt["native_exit_code"] == 0
    assert receipt["runtime"]["camera_enabled"] is False
    assert receipt["runtime"]["step_profile"]["candidate_validation"] is False


def test_malformed_new_step_admission_does_not_revoke_existing_step():
    owner = IntentOwner("ep", clock=lambda: 0.0, step_profile=StepProfile())
    token = owner.claim("fixture")["lease_token"]
    _submit(owner, token, "step", "step")
    owner.consume(sim_time=0.0)
    with serve(SnapshotStore(owner, runtime={"evidence_kind": "CPU_FIXTURE"}), port=0) as server:
        body = MotionCommand("ep", "other", 1, 0.1, 0, 0, 2.0).as_dict()
        headers = {"X-Workshop-Observation-Episode": "ep"}
        assert _post(server, "/v1/step", body, token, headers)[0] == 409
        assert owner.consume(sim_time=0.005) == (0.1, 0.0, 0.0)
        assert _post(server, "/v1/renew", {"episode_id": "ep"}, token, PROOF_HEADERS)[0] == 200
