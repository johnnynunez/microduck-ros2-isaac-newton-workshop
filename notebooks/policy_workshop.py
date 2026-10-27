"""Stdlib-only notebook handoff. Canonical safety validation stays in its image.

These checks bind bytes/source; they never replace the native physical evaluator.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import re

from workshop import Session


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    def reject(value):
        raise ValueError("nonfinite JSON: " + value)
    def number(value):
        result = float(value)
        if not math.isfinite(result):
            reject(value)
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject, parse_float=number)


def literal(path, name):
    """Read a source constant without importing NumPy/ROS/Kit into this kernel."""
    for node in ast.parse(Path(path).read_text()).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("Required source constant missing: " + name)


def control_sources(root):
    source = Path(root) / "src/microduck_workshop"
    names = literal(source / "policy/student.py", "SOURCE_FILES")
    return {name: sha256(source / name) for name in names}


def checked_file(directory, entry):
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise ValueError("malformed artifact entry")
    name, digest = entry["path"], entry["sha256"]
    if (not isinstance(name, str) or name in {"", ".", ".."} or Path(name).name != name
            or not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None):
        raise ValueError("invalid artifact path/hash")
    path = Path(directory) / name
    if path.is_symlink() or sha256(path) != digest:
        raise ValueError("artifact hash mismatch: " + name)
    return path


def training_bundle(root, run):
    run = Path(run).resolve()
    manifest_path = run / "policy_manifest.json"
    manifest = read_json(manifest_path)
    source = Path(root) / "src/microduck_workshop"
    parent = literal(source / "policy/contract.py", "POLICY_SHA256")
    if (manifest.get("schema_version") != 1 or manifest.get("kind") != "student_actor"
            or manifest.get("policy_mode") not in {"training", "deployment"}
            or manifest.get("input") != {"name": "obs", "shape": [1, 61]}
            or manifest.get("output") != {"name": "actions", "shape": [1, 14]}
            or manifest.get("parent_policy_sha256") != parent
            or manifest.get("source_sha256") != control_sources(root)):
        raise ValueError("manifest schema/control source mismatch")
    paths = {key: checked_file(run, manifest.get(key)) for key in ("actor", "checkpoint", "training_receipt")}
    receipt = read_json(paths["training_receipt"])
    if (receipt.get("actor_sha256") != manifest["actor"]["sha256"]
            or receipt.get("checkpoint_sha256") != manifest["checkpoint"]["sha256"]
            or receipt.get("actor_sha256") == parent
            or receipt.get("actor_changed_parameters", 0) <= 0
            or receipt.get("saved_optimizer_steps", 0) <= 0
            or receipt.get("physics_steps", 0) <= 0 or not receipt.get("updates")
            or receipt.get("evidence_kind") != "LIVE_MICRODUCK_NEWTON_PPO"
            or receipt.get("actor_init") != "public_v8_actor_only"
            or receipt.get("critic_init") != "fresh_random"
            or receipt.get("optimizer_init") != "fresh_adam"
            or receipt.get("full_ppo_resume") is not False
            or receipt.get("converged_gait") is not False):
        raise ValueError("not a changed, exported actor-only warm-start training run")
    if (receipt.get("training_source_sha256") != {n: sha256(source / "sim" / n) for n in ("train.py", "ppo.py")}
            or receipt.get("warmstart_source_sha256") != sha256(source / "policy/warmstart.py")):
        raise ValueError("training source changed")
    transitions = checked_file(run, receipt.get("transitions"))
    identity = {"checkpoint_sha256": sha256(paths["checkpoint"]),
                "policy_sha256": sha256(paths["actor"]), "manifest_sha256": sha256(manifest_path),
                "training_receipt_sha256": sha256(paths["training_receipt"])}
    return {"run": str(run), "identity": identity, "policy_mode": manifest["policy_mode"],
            "files": [str(p) for p in (*paths.values(), manifest_path, transitions)]}


def admitted_bundle(root, run, admission):
    bundle = training_bundle(root, run)
    admission = Path(admission).resolve()
    path = admission / "admission.json"
    value = read_json(path)
    if (value.get("passed") is not True
            or value.get("scope") != "native_only_not_ros_agent_acceptance"
            or value.get("policy_sha256") != bundle["identity"]["policy_sha256"]
            or value.get("manifest_sha256") != bundle["identity"]["manifest_sha256"]
            or value.get("policy_mode") != bundle["policy_mode"]
            or value.get("source_sha256") != control_sources(root) or not value.get("cases")):
        raise ValueError("admission missing, failed or identity/source mismatch; no agent motion")
    files = [checked_file(admission, entry) for case in value["cases"] for entry in case["artifacts"]]
    bundle["admission"] = str(admission)
    bundle["identity"]["admission_sha256"] = sha256(path)
    bundle["files"] += [str(p) for p in (path, *files)]
    # These are integrity prechecks only. verify_bundle invokes load_admission's
    # actual trace recomputation inside the prepared image before deployment.
    return bundle


def check_identity(health, identity, *, episode=None, previous_episode=None):
    runtime = health.get("runtime", {})
    profile = runtime.get("step_profile") or {}
    if (health.get("ready") is not True or health.get("physics") != "newton"
            or not health.get("episode_id") or (episode is not None and health["episode_id"] != episode)
            or runtime.get("isaacsim") != "6.2.0.0" or runtime.get("newton") != "1.6.1"
            or runtime.get("isaaclab_git_sha") != "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"
            or runtime.get("policy_sha256") != identity["policy_sha256"]
            or runtime.get("policy_manifest_sha256") != identity["manifest_sha256"]
            or profile.get("name") != "step-forward-v1"
            or profile.get("policy_sha256") != identity["policy_sha256"]
            or profile.get("admission_sha256") != identity["admission_sha256"]
            or profile.get("validation_status") != "NATIVE_VALIDATED"):
        raise ValueError("live policy/episode/runtime identity mismatch")
    if health["episode_id"] == previous_episode:
        raise ValueError("a fresh episode is required; never reuse/rearm the previous episode")
    # Intentionally do not expose raw health or evaluator state to the model.
    return dict(identity, episode_id=health["episode_id"], scope="identity_only_not_physical_acceptance")


class PolicySession(Session):
    def bundle_options(self, bundle):
        options = ["-v", f"{bundle['run']}:/policy-run:ro"]
        if "admission" in bundle:
            options += ["-v", f"{bundle['admission']}:/policy-admission:ro"]
        return options

    def source_options(self):
        return ["-e", "PYTHONPATH=/opt/workshop/src", "-v", f"{self.root / 'src'}:/opt/workshop/src:ro",
                "-v", f"{self.root / 'provenance'}:/opt/workshop/provenance:ro"]

    def course_options(self):
        options = [*self.source_options(), "-e", "PYTHONDONTWRITEBYTECODE=1",
                   "-e", "PYTEST_ADDOPTS=-p no:cacheprovider"]
        for directory in ("scripts", "tests", "exercises", "solutions"):
            options += ["-v", f"{self.root / directory}:/course/{directory}:ro"]
        return options

    def job(self, role, image, command, *, timeout, allowed=(0,), **kwargs):
        self.start(role, image, command, **kwargs)
        try:
            result = self.run(["docker", "wait", self.name(role)], timeout=timeout)
            code = int(result.stdout.strip())
            logs = self.run(["docker", "logs", self.name(role)])
            if code not in allowed:
                raise RuntimeError(f"{role} exit {code}; preserve this attempt, inspect logs; no retry")
            return code, logs.stdout
        finally:
            # docker wait timing out does NOT kill its container; do so by exact ownership.
            self.stop(role)

    def capabilities(self, image, *, agent=False):
        """Probe the image as shipped, before any source overlay; no GPU or network."""
        commands = [("microduck_workshop.agent.run", ("--policy-manifest", "--policy-admission", "--native-health-url", "--tools-file"))] if agent else [
            ("microduck_workshop.sim.train", ("--warm-start-onnx", "--updates", "--horizon")),
            ("microduck_workshop.sim.admit_policy", ("--policy-manifest", "--output")),
            ("microduck_workshop.sim.play", ("--policy-manifest", "--policy-admission", "--step-profile"))]
        for name, flags in commands:
            _, text = self.job("capability", image, [*(["python"] if agent else []), "-m", name, "--help"], timeout=60)
            if any(flag not in text for flag in flags):
                raise RuntimeError(f"Image {image} lacks student-policy API: {name}; ask staff for rebuilt image")
        if not agent:
            self.job("capability", image, ["-c", "from importlib.metadata import version; assert version('onnx') == '1.22.0', 'Require onnx==1.22.0'; print('onnx==1.22.0')"], timeout=60)

    def selection(self, stage):
        entry = self.require(stage)
        bundle = (admitted_bundle(self.root, entry["run"], entry["admission"])
                  if "admission" in entry else training_bundle(self.root, entry["run"]))
        if bundle["identity"] != entry["identity"]:
            raise ValueError("checkpoint/export/manifest/admission handoff identity changed")
        return bundle

    def verify_bundle(self, image, bundle):
        code = "from microduck_workshop.policy.student import load_manifest,load_admission; m=load_manifest('/policy-run/policy_manifest.json'); "
        if "admission" in bundle:
            code += "load_admission('/policy-admission/admission.json',m); "
        code += "print('Canonical artifact/source verification completed; not ROS/agent acceptance')"
        return self.job("verify-policy", image, ["-c", code], timeout=120,
                        options=[*self.source_options(), *self.bundle_options(bundle)])

    def start_policy(self, image, bundle, *, gpu, assets, url, previous_episode):
        self.verify_bundle(image, bundle)
        self.port_available(8766)
        output = self.new_output("student-serve")
        self.start("sim", image,
                   ["-m", "microduck_workshop.sim.play", "--asset-root", "/assets",
                    "--policy-manifest", "/policy-run/policy_manifest.json",
                    "--policy-admission", "/policy-admission/admission.json",
                    "--policy-mode", bundle["policy_mode"], "--step-profile", "step-forward-v1",
                    "--mode", "serve", "--steps", "0", "--cameras", "--head-camera-resolution", "320x240",
                    "--tag-id", "0", "--output", "/outputs/episode"],
                   options=[*self.sim_options(gpu, assets, output), *self.bundle_options(bundle)],
                   network="host", memory="32g", cpus=8)
        health = self.wait_sim(url)  # shared bounded cold-start + real sensor readiness
        identity = check_identity(health, bundle["identity"], previous_episode=previous_episode)
        return {**bundle, "episode_id": identity["episode_id"], "output": str(output)}

    def live_identity(self, url, bundle, episode, *, require_unstopped=True):
        self.owned("sim", running=True)
        health = (self.assert_episode(url, episode) if require_unstopped
                  else self.get_json(url + "/v1/health"))
        return check_identity(health, bundle["identity"], episode=episode)

    def claim_attempt(self, episode):
        state = self.state()
        if episode in state.get("attempts", []):
            raise RuntimeError("Agent attempt already claimed for this episode; no motion retry")
        state.setdefault("attempts", []).append(episode)
        self.save(state)  # Before process launch: an uncertain send consumes the attempt.
