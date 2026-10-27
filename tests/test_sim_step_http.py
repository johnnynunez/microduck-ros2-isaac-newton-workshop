import json
import urllib.error
import urllib.request

from microduck_workshop.policy.step import StepProfile
from microduck_workshop.sim.http import SnapshotStore, serve
from microduck_workshop.sim.intent import IntentOwner


def test_step_http_requires_proof_and_fresh_renewal():
    now = [10.0]
    owner = IntentOwner("ep", clock=lambda: now[0], step_profile=StepProfile())
    token = owner.claim("probe")["lease_token"]
    store = SnapshotStore(owner, runtime={"evidence_kind": "CPU_UNIT_TEST"})
    with serve(store, port=0) as server:

        def post(path, body, proof=None):
            headers = {"Content-Type": "application/json", "X-Workshop-Lease": token}
            headers.update(proof or {})
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}" + path,
                data=json.dumps(body).encode(),
                headers=headers,
            )
            try:
                with urllib.request.urlopen(req) as response:
                    return response.status, json.load(response)
            except urllib.error.HTTPError as error:
                return error.code, json.load(error)

        body = {
            "episode_id": "ep",
            "request_id": "s",
            "expected_generation": 0,
            "vx": 0.1,
            "vy": 0,
            "wz": 0,
            "duration_s": 2.0,
        }
        assert post("/v1/step", body)[0] == 409
        proof = {
            "X-Workshop-Observation-Episode": "ep",
            "X-Workshop-Observation-Sequence": "1",
            "X-Workshop-Observation-Deadline": "10.4",
        }
        code, receipt = post("/v1/step", body, proof)
        assert code == 200 and receipt["accepted"]
        assert "observation_deadline" not in receipt and "root_pose" not in receipt
        assert owner.consume(sim_time=0.0) == (0.1, 0.0, 0.0)
        assert post("/v1/renew", {"episode_id": "ep"}, proof)[0] == 200
        assert post("/v1/renew", {"episode_id": "ep"})[0] == 409
        assert owner.consume(sim_time=0.005) == (0.0, 0.0, 0.0)
        assert owner.status("s")["status"] == "expired"


def test_native_inference_routes_only_planned_step_to_step_conditioning():
    from microduck_workshop.contracts import MotionCommand
    from microduck_workshop.policy.calibration import CommandProfile
    from microduck_workshop.sim.intent import ObservationProof
    from microduck_workshop.sim.play import infer_owned_command, parser

    class Policy:
        def step(self, **kwargs):
            return "target", {"observed_command": list(kwargs["command"])}

    sample = {"imu": {"angular_velocity": [0] * 3}, "joint_position": [], "joint_velocity": []}
    owner = IntentOwner("ep", clock=lambda: 10.0, step_profile=StepProfile(True))
    token = owner.claim("probe")["lease_token"]
    owner.submit_step(
        MotionCommand("ep", "s", 0, 0.1, 0, 0, 2.0), token, ObservationProof("ep", 1, 10.4)
    )
    desired = owner.consume(sim_time=0.0)
    _, trace = infer_owned_command(Policy(), CommandProfile(), owner, sample, [0, 0, -1], desired)
    assert trace["neural_command"] == [0.25, 0.0, 0.0]
    assert trace["maneuver_phase"] == "drive"
    desired = owner.consume(sim_time=1.0)
    _, trace = infer_owned_command(Policy(), CommandProfile(), owner, sample, [0, 0, -1], desired)
    assert trace["neural_command"] == [0.0, 0.0, 0.0]
    assert trace["requested_peak_command"] == [0.1, 0, 0]
    assert trace["maneuver_phase"] == "settle"
    args = parser().parse_args(["--asset-root", "assets", "--step-profile", "step-forward-v1"])
    assert args.command_profile == "direct"
    assert not args.step_candidate_validation
