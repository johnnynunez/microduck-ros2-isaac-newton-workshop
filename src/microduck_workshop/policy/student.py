"""Source-bound student artifacts. Explicit selection always fails closed.

Receipts are local reproducibility evidence, not signed security credentials.
Native admission does not assert ROS/perception or agent acceptance.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from microduck_workshop.contracts import ContractError

from .contract import DECIMATION, HOME, PHYSICS_DT, POLICY_SHA256
from .onnx import VelStandPolicy
from .step import STEP_NAME, StepProfile

SOURCE_FILES = (
    "contracts.py",
    "policy/contract.py",
    "policy/imu.py",
    "policy/onnx.py",
    "policy/step.py",
    "policy/student.py",
    "sim/native.py",
    "sim/prepare.py",
    "sim/bam.py",
    "sim/joint_map.py",
    "sim/play.py",
    "sim/evaluate.py",
    "sim/intent.py",
    "sim/http.py",
    "sim/admit_policy.py",
)
ADMISSION_CASES = (
    ("h1-w04", 0.4, 0.4),
    ("h2-w08", 0.8, 0.8),
    ("h3-w14", 1.4, 1.4),
    ("confirmation-w11", 1.3, 1.1),
)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: sha256(root / name) for name in SOURCE_FILES}


def read_json(path):
    def reject(value):
        raise ValueError(f"nonfinite JSON: {value}")

    value = json.loads(Path(path).read_text(), parse_constant=reject)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")  # noqa: TRY004 -- malformed serialized input
    return value


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def artifact(path):
    return {"path": Path(path).name, "sha256": sha256(path)}


def checked_artifact(directory, entry):
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise ValueError("malformed artifact entry")
    name, digest = entry["path"], entry["sha256"]
    if (
        not isinstance(name, str)
        or name in {"", ".", ".."}
        or Path(name).name != name
        or not isinstance(digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", digest) is None
    ):
        raise ValueError("invalid artifact path/hash")
    path = Path(directory) / name
    if path.is_symlink() or sha256(path) != digest:
        raise ValueError(f"artifact hash mismatch: {name}")
    return path


def create_manifest(output, *, mode):
    output = Path(output)
    value = {
        "schema_version": 1,
        "kind": "student_actor",
        "actor": artifact(output / "actor.onnx"),
        "checkpoint": artifact(output / "checkpoint.pt"),
        "training_receipt": artifact(output / "training_receipt.json"),
        "parent_policy_sha256": POLICY_SHA256,
        "policy_mode": mode,
        "input": {"name": "obs", "shape": [1, 61]},
        "output": {"name": "actions", "shape": [1, 14]},
        "source_sha256": source_hashes(),
        "admission": "not_admitted",
    }
    write_json(output / "policy_manifest.json", value)
    return value


def load_manifest(path):
    path = Path(path).resolve()
    value = read_json(path)
    if (
        value.get("schema_version") != 1
        or value.get("kind") != "student_actor"
        or value.get("policy_mode") not in {"training", "deployment"}
        or value.get("input") != {"name": "obs", "shape": [1, 61]}
        or value.get("output") != {"name": "actions", "shape": [1, 14]}
        or value.get("parent_policy_sha256") != POLICY_SHA256
        or value.get("source_sha256") != source_hashes()
    ):
        raise ValueError("manifest schema/control source mismatch")
    paths = {
        name: checked_artifact(path.parent, value.get(name))
        for name in ("actor", "checkpoint", "training_receipt")
    }
    training = read_json(paths["training_receipt"])
    if (
        training.get("checkpoint_sha256") != value["checkpoint"]["sha256"]
        or training.get("actor_sha256") != value["actor"]["sha256"]
        or value["actor"]["sha256"] == POLICY_SHA256
        or training.get("actor_changed_parameters", 0) <= 0
        or training.get("saved_optimizer_steps", 0) <= 0
    ):
        raise ValueError("manifest does not bind a changed trained actor")
    validate_training_receipt(training, value, path.parent)
    return dict(
        value,
        raw_action_parity={
            "atol": training["export_parity"]["atol"],
            "rtol": training["export_parity"]["rtol"],
        },
        manifest_sha256=sha256(path),
        manifest_path=path,
        actor_path=paths["actor"],
        policy_sha256=value["actor"]["sha256"],
    )


def validate_training_receipt(training, manifest, directory):
    """Check relevant native update metadata, not arbitrary positive counters."""
    root = Path(__file__).resolve().parents[1]
    updates = training.get("updates", [])
    if (
        training.get("evidence_kind") != "LIVE_MICRODUCK_NEWTON_PPO"
        or training.get("actor_init") != "public_v8_actor_only"
        or training.get("critic_init") != "fresh_random"
        or training.get("optimizer_init") != "fresh_adam"
        or training.get("full_ppo_resume") is not False
        or training.get("parent_policy_sha256") != POLICY_SHA256
        or training.get("policy_mode") != manifest["policy_mode"]
        or training.get("training_source_sha256")
        != {name: sha256(root / "sim" / name) for name in ("train.py", "ppo.py")}
        or training.get("warmstart_source_sha256") != sha256(root / "policy/warmstart.py")
        or training.get("runtime", {}).get("physics_owner")
        != "isaaclab_newton.physics.NewtonManager"
        or training.get("bam", {}).get("delay_physics_steps") != DECIMATION
        or training.get("bam", {}).get("friction_native_verified") is not True
        or not updates
    ):
        raise ValueError("training receipt metadata/source mismatch")
    for i, update in enumerate(updates):
        if (
            update.get("update") != i
            or type(update.get("optimizer_steps")) is not int
            or update["optimizer_steps"] != (i + 1) * 4
            or not all(
                np.isfinite(update.get(key, float("nan"))) and update.get(key, 0) > 0
                for key in ("actor_weight_delta_l2", "gradient_norm")
            )
        ):
            raise ValueError("training receipt update metadata mismatch")
    if training["saved_optimizer_steps"] != updates[-1]["optimizer_steps"]:
        raise ValueError("training receipt optimizer step mismatch")
    checked_artifact(directory, {"path": "initial.pt", "sha256": training.get("initial_sha256")})
    transitions = checked_artifact(directory, training.get("transitions"))
    samples = len(transitions.read_text().splitlines())
    if not samples or training.get("physics_steps") != samples * DECIMATION:
        raise ValueError("training receipt native transition count mismatch")
    for name in ("warmstart_parity", "export_parity"):
        parity = training.get(name, {})
        if (
            parity.get("samples") != samples
            or parity.get("atol") != 2e-5
            or parity.get("rtol") != 2e-5
            or not 0 <= parity.get("max_abs_error", float("inf")) <= 2e-5
            or parity.get("inputs") != "recorded_native_encoder_imu_command_previous_raw"
        ):
            raise ValueError("training receipt numerical parity metadata mismatch")


class StudentPolicy(VelStandPolicy):
    """Reuse the exact canonical observation/previous-RAW/target pipeline."""

    def __init__(self, manifest):
        import onnx
        import onnxruntime as ort
        from onnx import numpy_helper

        if not isinstance(manifest, dict):
            manifest = load_manifest(manifest)
        path = manifest["actor_path"]
        # Recheck bytes at selection; no accepted path is a fallback instruction.
        raw = Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["policy_sha256"]:
            raise ValueError("actor hash changed after manifest load")
        graph = onnx.load_model_from_string(raw)
        if any(t.data_location == onnx.TensorProto.EXTERNAL for t in graph.graph.initializer):
            raise ValueError("external tensor data is not permitted")
        onnx.checker.check_model(graph)
        if any(not np.isfinite(numpy_helper.to_array(t)).all() for t in graph.graph.initializer):
            raise ValueError("nonfinite ONNX initializer")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            raw, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        ins, outs = self.session.get_inputs(), self.session.get_outputs()
        if (
            len(ins) != 1
            or ins[0].name != "obs"
            or ins[0].shape != [1, 61]
            or ins[0].type != "tensor(float)"
            or len(outs) != 1
            or outs[0].name != "actions"
            or outs[0].shape != [1, 14]
            or outs[0].type != "tensor(float)"
        ):
            raise ValueError("unexpected student ONNX input/output contract")
        probe = self.session.run(None, {"obs": np.zeros((1, 61), np.float32)})[0]
        if not np.isfinite(probe).all():
            raise ValueError("nonfinite ONNX output")
        self.mode, self.sha256 = manifest["policy_mode"], manifest["policy_sha256"]
        self.previous_raw = np.zeros(14, np.float32)
        self.previous_target = HOME.copy()
        self.manifest = manifest


def fixed_step_spec():
    return {
        "name": STEP_NAME,
        "requested_peak": [0.1, 0.0, 0.0],
        "drive_neural_command": [0.25, 0.0, 0.0],
        "drive_s": 1.0,
        "settle_neural_command": [0.0, 0.0, 0.0],
        "settle_s": 1.0,
        "horizon_s": 2.0,
        "verifier_wait_s": 0.36,
    }


def admission_plan():
    return [
        {"id": name, "initial_zero_s": initial, "zero_wait_s": wait}
        for name, initial, wait in ADMISSION_CASES
    ]


def case_schedule(case_id):
    """Integer control ticks; no trace labels or serialized plan define coverage."""
    dt = DECIMATION * PHYSICS_DT
    spec = fixed_step_spec()
    start = 0
    for name, initial, wait in ADMISSION_CASES:
        rows = []

        def add(seconds, phase, drive=False):
            count = round(seconds / dt)
            if not np.isclose(count * dt, seconds, atol=1e-12, rtol=0):
                raise ValueError("admission timing is not an integer control period")
            rows.extend([(phase, drive)] * count)

        add(initial, "initial_zero")
        for request in ("step", "resume"):
            add(spec["drive_s"], request, True)
            add(spec["settle_s"], request)
            add(spec["verifier_wait_s"], request + "_verify_wait")
            add(wait - spec["verifier_wait_s"], request + "_remaining_zero_wait")
        add(1.0 + spec["verifier_wait_s"], "rest_control")
        if name == case_id:
            return start, rows
        start += len(rows)
    raise ValueError("unknown admission case")


def load_admission(path, manifest, *, replay_policy=None):
    """Structural/physical readback; native selection MUST supply replay_policy.

    Identity-only readers intentionally need neither ONNX constructors nor Torch.
    They do not authorize motion. select_student and the native supervisor replay.
    """
    value = read_json(path)
    if (
        value.get("schema_version") != 1
        or value.get("passed") is not True
        or "error" in value
        or value.get("lifecycle") != "complete"
        or value.get("plan") != admission_plan()
        or value.get("scope") != "native_only_not_ros_agent_acceptance"
        or value.get("policy_sha256") != manifest.get("policy_sha256")
        or value.get("manifest_sha256") != manifest.get("manifest_sha256")
        or value.get("policy_mode") != manifest.get("policy_mode")
        or value.get("source_sha256") != source_hashes()
        or value.get("fixed_step") != fixed_step_spec()
        or not value.get("cases")
    ):
        raise ValueError("policy admission missing, failed, or binding mismatch")
    if [c.get("id") for c in value["cases"]] != [c[0] for c in ADMISSION_CASES]:
        raise ValueError("incomplete or altered admission holdout cases")
    runtime = value.get("runtime", {})
    if (
        runtime.get("isaacsim") != "6.2.0.0"
        or runtime.get("newton") != "1.6.1"
        or runtime.get("isaaclab_git_sha") != "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"
        or value.get("bam", {}).get("delay_physics_steps") != 4
        or value.get("bam", {}).get("friction_native_verified") is not True
    ):
        raise ValueError("admission runtime/BAM identity mismatch")
    for case in value["cases"]:
        if (
            [v.get("request") for v in case.get("verdicts", [])]
            != ["step", "resume", "rest_control"]
            or not all(v.get("verified") is True for v in case["verdicts"])
            or len(case.get("artifacts", [])) != 2
        ):
            raise ValueError("policy admission has failing physical verdicts")
        for entry in case.get("artifacts", []):
            checked_artifact(Path(path).parent, entry)
        verify_case_trace(Path(path).parent, case, manifest, replay_policy=replay_policy)
    total = sum(len(case_schedule(name)[1]) for name, _, _ in ADMISSION_CASES)
    if type(value.get("physics_steps")) is not int or value["physics_steps"] != total * DECIMATION:
        raise ValueError("admission physics step coverage mismatch")
    return dict(value, admission_sha256=sha256(path))


def verify_case_trace(directory, case, manifest, *, replay_policy=None):
    """Recompute unchanged physical gates, never trust a serialized passed boolean."""
    from types import SimpleNamespace

    from microduck_workshop.sim.evaluate import evaluate_motion

    from .contract import targets

    expected = [f"{case['id']}_{suffix}.jsonl" for suffix in ("policy", "truth")]
    if [a["path"] for a in case["artifacts"]] != expected:
        raise ValueError("admission trace artifact names mismatch")
    policy, truth = [
        [json.loads(line) for line in (directory / name).read_text().splitlines()]
        for name in expected
    ]
    if len(policy) != len(truth) or not policy:
        raise ValueError("admission trace length mismatch")
    start, schedule = case_schedule(case["id"])
    if len(policy) != len(schedule):
        raise ValueError("admission complete control-step coverage mismatch")
    if replay_policy is not None and (
        replay_policy.sha256 != manifest["policy_sha256"]
        or replay_policy.mode != manifest["policy_mode"]
    ):
        raise ValueError("admission replay actor binding mismatch")
    profile = CandidateStepProfile(
        SimpleNamespace(sha256=manifest["policy_sha256"], mode=manifest["policy_mode"])
    ).receipt()
    previous_raw, previous_target = np.zeros(14, np.float32), HOME.copy()
    for index, (neural, physical, (phase, drive)) in enumerate(zip(policy, truth, schedule)):
        # Times are produced by repeated binary-float physics additions. 1ns
        # admits only rounding noise, never a missing 5ms/20ms native/control tick.
        for row, tick in ((neural, start + index), (physical, start + index + 1)):
            if (
                row.get("phase") != phase
                or not np.isfinite(row.get("sim_time", float("nan")))
                or not np.isclose(
                    row["sim_time"], tick * DECIMATION * PHYSICS_DT, atol=1e-9, rtol=0
                )
            ):
                raise ValueError("admission phase/control-step chronology mismatch")
        command = [0.25, 0.0, 0.0] if drive else [0.0, 0.0, 0.0]
        desired = [0.1, 0.0, 0.0] if drive else [0.0, 0.0, 0.0]
        if (
            neural.get("neural_command") != command
            or neural.get("desired_command") != desired
            or neural.get("command_profile") != profile
        ):
            raise ValueError("admission scheduled command/profile mismatch")
        obs, raw = np.asarray(neural["observation"]), np.asarray(neural["raw_action"])
        if (
            neural["policy_sha256"] != manifest["policy_sha256"]
            or neural["mode"] != manifest["policy_mode"]
            or obs.shape != (61,)
            or raw.shape != (14,)
            or not np.isfinite(obs).all()
            or not np.isfinite(raw).all()
            or not np.array_equal(obs[34:48], previous_raw)
            or not np.isclose(np.linalg.norm(obs[3:6]), 1, atol=0.02)
            or not np.array_equal(obs[48:51], np.asarray(command, np.float32))
            or not np.array_equal(obs[51:], np.zeros(10))
        ):
            raise ValueError("admission policy trace contract mismatch")
        if replay_policy is not None:
            actual_raw = replay_policy.session.run(
                ["actions"], {"obs": obs.astype(np.float32)[None]}
            )[0][0]
            tolerance = manifest["raw_action_parity"]
            if not np.isfinite(actual_raw).all() or not np.allclose(actual_raw, raw, **tolerance):
                raise ValueError("admission ONNX output/raw action mismatch")
        for key, size in (("root_pose", 7), ("root_velocity", 6)):
            data = np.asarray(physical.get(key))
            if data.shape != (size,) or not np.isfinite(data).all():
                raise ValueError("admission physical sample contract mismatch")
        target = targets(raw, mode=manifest["policy_mode"], previous_target=previous_target)
        if not np.array_equal(target, neural["target"]):
            raise ValueError("admission action filter mismatch")
        previous_raw, previous_target = raw, target
    for reported in case["verdicts"]:
        name = reported["request"]
        indices = [
            i for i, row in enumerate(truth) if row["phase"] in {name, name + "_verify_wait"}
        ]
        expected_count = 68 if name == "rest_control" else 118
        if len(indices) != expected_count or indices[0] == 0:
            raise ValueError("admission physical trace coverage mismatch")
        rows = [truth[indices[0] - 1]] + [truth[i] for i in indices]
        if name != "rest_control":
            commands = [r["neural_command"] for r in policy if r["phase"] == name]
            if commands != [[0.25, 0.0, 0.0]] * 50 + [[0.0, 0.0, 0.0]] * 50:
                raise ValueError("admission fixed step command mismatch")
        command = SimpleNamespace(
            vx=0.0 if name == "rest_control" else 0.1,
            wz=0.0,
            duration_s=1.0 if name == "rest_control" else 2.0,
        )
        actual = dict(request=name, **evaluate_motion(rows, command, "completed"))
        if actual != reported or actual["verified"] is not True:
            raise ValueError("admission recomputed physical verdict mismatch")


class StudentDirectProfile:
    name = "direct"

    def __init__(self, policy):
        self.policy = policy

    def bind(self, *, policy_sha256, policy_mode):
        if policy_sha256 != self.policy.sha256 or policy_mode != self.policy.mode:
            raise ValueError("student profile binding mismatch")

    def condition(self, desired):
        return tuple(desired)

    def validate_request(self, command):
        if (command.vx, command.vy, command.wz) != (0, 0, 0):
            raise ContractError("student policy is admitted only for the exact fixed step")

    def receipt(self):
        return {
            "name": self.name,
            "policy_sha256": self.policy.sha256,
            "policy_mode": self.policy.mode,
            "nonzero_direct_motion": "NOT_READY",
        }


class CandidateStepProfile(StudentDirectProfile):
    name = STEP_NAME

    def phase(self, elapsed):
        return StepProfile(True).phase(elapsed)

    def condition(self, desired):
        return StepProfile(True).condition(desired)

    def validate_request(self, command):
        raise ContractError("candidate student policy is not admitted")

    def receipt(self):
        return dict(
            fixed_step_spec(),
            policy_sha256=self.policy.sha256,
            policy_mode=self.policy.mode,
            validation_status="UNVALIDATED",
            candidate_validation=True,
            online_feedback=False,
        )


class StudentStepProfile(CandidateStepProfile):
    def __init__(self, policy, admission):
        super().__init__(policy)
        self.admission = admission

    def validate_request(self, command):
        StepProfile(True).validate_request(command)

    def receipt(self):
        spec = dict(
            fixed_step_spec(),
            policy_sha256=self.policy.sha256,
            policy_mode=self.policy.mode,
            validation_status="NATIVE_VALIDATED",
            admission_sha256=self.admission["admission_sha256"],
            candidate_validation=False,
            online_feedback=False,
            production_requires_observation_proof=True,
            scope="native_only_not_ros_agent_acceptance",
        )
        spec["profile_sha256"] = hashlib.sha256(
            json.dumps(spec, sort_keys=True).encode()
        ).hexdigest()
        return spec


def select_student(
    manifest_path,
    *,
    mode,
    policy_mode,
    command_profile,
    step_profile,
    candidate_validation=False,
    admission_path=None,
):
    if candidate_validation or command_profile != "direct":
        raise ValueError("student selection forbids canonical/candidate profile substitution")
    manifest = load_manifest(manifest_path)
    if manifest["policy_mode"] != policy_mode:
        raise ValueError("policy mode does not match training manifest")
    policy = StudentPolicy(manifest)
    admission = None
    if mode == "serve":
        if admission_path is None:
            raise ValueError("student serve requires exact-policy native admission")
        admission = load_admission(admission_path, manifest, replay_policy=policy)
    elif admission_path is not None:
        admission = load_admission(admission_path, manifest, replay_policy=policy)
    if step_profile != "disabled" and admission is None:
        raise ValueError("step profile requires exact-policy admission")
    return (
        policy,
        StudentDirectProfile(policy),
        StudentStepProfile(policy, admission) if step_profile != "disabled" else None,
    )
