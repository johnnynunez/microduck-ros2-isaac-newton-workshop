"""Small, transparent host helpers. ROS, CUDA and Kit stay in their containers.

Commands are printed before execution; full output stays under .workshop, not in git.
This is orchestration, never an alternative safety/physics implementation.
"""
from pathlib import Path
import os
import hashlib
import json
import re
import uuid
import shlex
import subprocess
import time
import math
import socket
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


class SensorNotReady(RuntimeError):
    """A read-only startup poll may wait for a new capture, never restamp it."""


def startup_timeout(value=None):
    try:
        value = float(os.environ.get("WORKSHOP_SIM_STARTUP_TIMEOUT", "600") if value is None else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("startup timeout must be finite and in (0, 1800] seconds") from exc
    if not math.isfinite(value) or not 0 < value <= 1800:
        raise ValueError("startup timeout must be finite and in (0, 1800] seconds")
    return value


def check_camera(headers, payload, episode):
    if headers.get("X-Microduck-Episode") != episode:
        raise RuntimeError("Camera episode changed; do not reuse prior observations")
    age = time.monotonic() - float(headers.get("X-Microduck-Capture-Monotonic", "nan"))
    if not math.isfinite(age) or not 0 <= age <= 0.5:
        raise SensorNotReady("Camera capture is stale, future-dated or nonfinite")
    try:
        sequence = headers["X-Microduck-Sequence"]
        sim_time = float(headers["X-Microduck-Sim-Time"])
        if not re.fullmatch(r"[0-9]+", sequence) or not math.isfinite(sim_time) or sim_time < 0:
            raise ValueError("invalid sequence/simulation time")
    except (ValueError, KeyError, TypeError) as exc:
        raise SensorNotReady("Camera capture header is missing or malformed") from exc
    if not payload.startswith(b"\xff\xd8") or not payload.endswith(b"\xff\xd9"):
        raise SensorNotReady("Camera endpoint did not return a JPEG")


def find_root(start=None):
    start = Path(start or os.environ.get("WORKSHOP_ROOT", Path.cwd())).resolve()
    for path in (start, *start.parents):
        if (path / "pyproject.toml").is_file() and (path / "src/microduck_workshop").is_dir():
            return path
    raise RuntimeError("Cannot find workshop repository; set WORKSHOP_ROOT to its checkout")


class Session:
    def __init__(self, root=None, *, work=None):
        self.root = find_root(root)
        self.work = Path(work or self.root / ".workshop/notebooks").resolve()
        (self.work / "logs").mkdir(parents=True, exist_ok=True)

    def state(self):
        path = self.work / "state.json"
        if not path.exists():
            path.write_text(json.dumps({"owner": uuid.uuid4().hex[:10], "stages": {}}))
        return json.loads(path.read_text())

    def save(self, state):
        path = self.work / "state.tmp"
        path.write_text(json.dumps(state, indent=2))
        path.replace(self.work / "state.json")

    def source_digest(self):
        digest = hashlib.sha256()
        paths = sorted((self.root / "src").rglob("*.py"))
        paths += sorted((self.root / "provenance").glob("*.json"))
        for path in paths:
            digest.update(str(path.relative_to(self.root)).encode() + b"\0" + path.read_bytes())
        return digest.hexdigest()

    def complete(self, stage, data, *, artifacts=()):
        state = self.state()
        # Diagnostic provenance, not an answer-file hash or a new admission
        # authority. Keep the existing runtime-source/artifact invalidation.
        paths = [p for p in (self.root / "notebooks").glob("*.py") if p.is_file()]
        paths += [p for p in (self.root / "ros_ws/src").rglob("*")
                  if p.is_file() and p.suffix in {".py", ".xml", ".msg", ".srv", ".yaml", ".txt"}]
        state["stages"][stage] = {"data": data, "source_sha256": self.source_digest(), "artifacts": {
            str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest()
            for p in artifacts}, "provenance": {
                "source_sha256": {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(paths)},
                "images": state.get("container_images", {}).copy()}}
        # Repeating an earlier notebook invalidates dependent checkpoints.
        for later in list(state["stages"]):
            if later > stage:
                del state["stages"][later]
        self.save(state)

    def require(self, stage):
        entry = self.state()["stages"].get(stage)
        if not entry:
            raise RuntimeError(f"Notebook {stage} checkpoint missing; run it first")
        if entry.get("source_sha256") != self.source_digest():
            raise RuntimeError(f"Workshop source changed; repeat notebook {stage} on the current release")
        for name, digest in entry["artifacts"].items():
            if not Path(name).is_file() or hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
                raise RuntimeError(f"Artifact missing or changed: {name}; repeat notebook {stage}")
        return entry["data"]

    def name(self, role):
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,25}", role):
            raise ValueError("invalid container role")
        prefix = os.environ.get("WORKSHOP_NOTEBOOK_PREFIX", "roscon-nb")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,30}", prefix):
            raise ValueError("invalid notebook container prefix")
        return prefix + "-" + self.state()["owner"] + "-" + role

    def container_command(self, role, image, command, *, options=(), network="none", memory="4g", cpus=2):
        domain = os.environ.get("WORKSHOP_ROS_DOMAIN", "71")
        if not domain.isdigit() or not 0 <= int(domain) <= 232:
            raise ValueError("ROS domain must be an integer in 0..232")
        return ["docker", "run", "-d", "--name", self.name(role), "--init",
                "--label", "workshop.notebook.owner=" + self.state()["owner"],
                "--restart", "no", "--memory", memory, "--cpus", str(cpus), "--network", network,
                "-e", "ROS_DOMAIN_ID=" + domain, "-e", "ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST",
                *map(str, options), image, *map(str, command)]

    def gpu_options(self, gpu):
        if not re.fullmatch(r"[0-9]+", str(gpu)):
            raise ValueError("Select exactly one numeric physical GPU index")
        selector = os.environ.get("WORKSHOP_GPU_SELECTOR", "gpus")
        if selector == "cdi":
            selection = ["--device", "nvidia.com/gpu=" + str(gpu)]
        elif selector == "gpus":
            selection = ["--gpus", "device=" + str(gpu)]
        else:
            raise ValueError("WORKSHOP_GPU_SELECTOR must be gpus or cdi")
        return [*selection, "-e", "NVIDIA_DRIVER_CAPABILITIES=graphics,compute,utility"]

    def gpu_preflight(self, gpu, *, accept_eula):
        if accept_eula is not True:
            raise RuntimeError("NVIDIA EULA must be reviewed and explicitly accepted")
        self.gpu_options(gpu)
        self.run(["nvidia-smi", "-i", str(gpu), "--query-gpu=index,uuid,name,memory.free",
                  "--format=csv"], timeout=15)
        print("Confirm this GPU allocation with staff; free VRAM is not exclusive ownership.")

    def sim_options(self, gpu, assets, output):
        assets, output = Path(assets).resolve(), Path(output).resolve()
        for relative in ("robot/robot_allcollisions_backlash.xml", "policies/velstand.onnx"):
            if not (assets / relative).is_file():
                raise RuntimeError(f"Prepared public asset missing: {relative}; use scripts/sim_setup.sh")
        home = self.work / "sim-home"
        home.mkdir(exist_ok=True)
        return [*self.gpu_options(gpu), "--shm-size", "2g", "-e", "OMNI_KIT_ACCEPT_EULA=YES",
                "-e", "OMNI_KIT_ALLOW_ROOT=1", "-e", "HOME=/sim-home",
                "-e", "PYTHONPATH=/opt/workshop/src", "-v", f"{self.root / 'src'}:/opt/workshop/src:ro",
                "-v", f"{self.root / 'provenance'}:/opt/workshop/provenance:ro",
                "-v", f"{assets}:/assets:ro", "-v", f"{output}:/outputs", "-v", f"{home}:/sim-home"]

    def new_output(self, label):
        if not re.fullmatch(r"[a-z0-9-]+", label):
            raise ValueError("invalid output label")
        path = self.work / "runs" / (label + "-" + uuid.uuid4().hex[:12])
        path.mkdir(parents=True, exist_ok=False)
        return path

    def port_available(self, port):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", int(port)))
            except OSError as exc:
                raise RuntimeError(f"Port {port} occupied; no existing process will be stopped") from exc

    def get(self, url, *, timeout=3.0):
        parsed = urlsplit(url)
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.username or parsed.password:
            raise ValueError("Only credential-free HTTP loopback URLs are permitted")
        # No proxy credentials, environment proxies, external redirects or API keys.
        from urllib.request import HTTPRedirectHandler
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, *_args, **_kwargs):
                raise ValueError("loopback endpoint redirect refused")
        with build_opener(ProxyHandler({}), NoRedirect()).open(url, timeout=timeout) as response:
            return dict(response.headers), response.read(8 * 1024 * 1024)

    def get_json(self, url, *, timeout=3.0):
        return json.loads(self.get(url, timeout=timeout)[1])

    def wait_ros_node(self, role, node, *, timeout=60):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            result = self.ros(role, ["node", "list", "--no-daemon", "--spin-time", "1"])
            if node in result.stdout.splitlines():
                return
            time.sleep(1)
        raise RuntimeError(f"Node {node} readiness deadline exceeded; inspect container logs")

    def wait_sim(self, url, *, timeout=None):
        timeout = startup_timeout(timeout)
        self.owned("sim", running=True)
        deadline = time.monotonic() + timeout
        last_error = "no response"
        while time.monotonic() < deadline:
            try:
                health = self.get_json(url + "/v1/health", timeout=min(3, deadline - time.monotonic()))
                if not health.get("ready"):
                    raise ValueError("not ready")
                if health["physics"] != "newton" or health["runtime"]["isaacsim"] != "6.2.0.0":
                    raise RuntimeError("Unexpected native physics/runtime identity")
                # Physics may publish state before its first camera render. Use
                # the SAME startup budget; health alone is not sensor readiness.
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                return self.wait_sensors(url, expected_episode=health["episode_id"],
                                         timeout=remaining)["health"]
            except (OSError, ValueError, KeyError) as exc:
                last_error = str(exc)
                time.sleep(min(1, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"Simulator readiness deadline exceeded: {last_error}")

    def wait_sensors(self, url, *, expected_episode, timeout=None):
        """GET-only readiness, not authority or a cached observation for motion.

        Keep original timestamps; stale/missing input can only be replaced by
        a new producer sample. Episode changes and STOP fail immediately.
        """
        deadline = time.monotonic() + startup_timeout(timeout)
        self.owned("sim", running=True)
        last_error = "no sensor response"

        def read(path, *, binary=False):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SensorNotReady("sensor read deadline")
            return (self.get if binary else self.get_json)(url + path, timeout=min(3, remaining))

        while time.monotonic() < deadline:
            try:
                health = read("/v1/health")
                if health.get("episode_id") != expected_episode:
                    raise RuntimeError("Simulator episode changed; no readiness retry across episodes")
                if not health.get("ready"):
                    raise SensorNotReady("native state not ready")
                if health.get("physics") != "newton" or health.get("runtime", {}).get("isaacsim") != "6.2.0.0":
                    raise RuntimeError("Unexpected native physics/runtime identity")
                state = read("/v1/state")
                if state.get("episode_id") != expected_episode:
                    raise RuntimeError("State episode changed; no readiness retry across episodes")
                if state.get("stop_latched"):
                    raise RuntimeError("Episode is stopped; no automatic re-arm or retry")
                info = read("/v1/camera_info")
                if not info.get("frame_id") or info.get("width", 0) <= 0 or info.get("height", 0) <= 0:
                    raise SensorNotReady("camera calibration unavailable")
                headers, payload = read("/v1/camera", binary=True)
                check_camera(headers, payload, expected_episode)
                # Check at the end: camera/calibration latency counts against
                # the original state's unchanged 0.5-second freshness budget.
                age = time.monotonic() - float(state.get("capture_monotonic_s", "nan"))
                if not math.isfinite(age) or not 0 <= age <= 0.5:
                    raise SensorNotReady("State capture is stale, future-dated or nonfinite")
                if time.monotonic() >= deadline:
                    raise SensorNotReady("sensor read deadline")
                return {"health": health, "state": state, "camera_info": info,
                        "headers": headers, "payload": payload}
            except (OSError, ValueError, KeyError, SensorNotReady) as exc:
                last_error = str(exc)
                time.sleep(min(.1, max(0, deadline - time.monotonic())))
        raise RuntimeError(f"Sensor readiness deadline exceeded: {last_error}")

    def assert_episode(self, url, episode):
        self.owned("sim", running=True)
        health = self.get_json(url + "/v1/health")
        if not health.get("ready") or health.get("episode_id") != episode:
            raise RuntimeError("Simulator restarted or not ready; prior episode checkpoint is invalid")
        state = self.get_json(url + "/v1/state")
        if state.get("stop_latched"):
            raise RuntimeError("Episode is stopped; no automatic re-arm or retry")
        return health

    def camera_snapshot(self, url, *, expected_episode, label):
        capture = self.wait_sensors(url, expected_episode=expected_episode)
        headers, payload = capture["headers"], capture["payload"]
        directory = self.new_output(label)
        path = directory / "head.jpg"
        path.write_bytes(payload)
        (directory / "capture.json").write_text(json.dumps(headers, indent=2))
        print("Actual onboard snapshot; episode:", expected_episode,
              "sequence:", headers.get("X-Microduck-Sequence"))
        return path

    def start(self, role, image, command, **kwargs):
        # Never adopt/restart an existing container, even one with our old name.
        self.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
        result = self.run(self.container_command(role, image, command, **kwargs))
        state = self.state()
        state.setdefault("containers", {})[role] = result.stdout.strip()
        self.save(state)
        # Read the actual container, not just a mutable image tag at preflight.
        # Ownership is persisted first so an inspect failure remains cleanable.
        image_id = self.run(["docker", "inspect", "--format", "{{.Image}}", result.stdout.strip()]).stdout.strip()
        state.setdefault("container_images", {})[role] = {
            "reference": image, "image_id": image_id, "container_id": result.stdout.strip()}
        self.save(state)
        return result

    def owned(self, role, *, running=False):
        expected = self.state().get("containers", {}).get(role)
        if not expected:
            raise RuntimeError(f"No owned {role} container; rerun its explicit start cell")
        result = self.run(["docker", "inspect", "--format",
                           '{{.Id}} {{index .Config.Labels "workshop.notebook.owner"}} {{.State.Running}}',
                           self.name(role)])
        fields = result.stdout.strip().split()
        if len(fields) != 3 or fields[:2] != [expected, self.state()["owner"]]:
            raise RuntimeError("Container ownership mismatch; no action taken")
        if running and fields[2] != "true":
            raise RuntimeError(f"Owned {role} container is not running; inspect its logs")
        return expected

    def ros(self, role, args, *, timeout=15):
        self.owned(role, running=True)
        return self.run(["docker", "exec", self.name(role), "bash", "/opt/workshop/entrypoint.sh",
                         "timeout", "--signal=INT", str(timeout), "ros2", *args],
                        timeout=timeout + 5)

    def stop(self, role):
        if role not in self.state().get("containers", {}):
            print(f"No owned {role} container recorded; nothing stopped")
            return
        self.owned(role)
        self.run(["docker", "stop", "--time", "8", self.name(role)], timeout=20)
        self.run(["docker", "logs", self.name(role)], timeout=15)
        self.run(["docker", "rm", self.name(role)])
        result = self.run(["docker", "container", "ls", "-a", "--filter",
                           "name=^/" + self.name(role) + "$", "--format", "{{.ID}}"])
        if result.stdout.strip():
            raise RuntimeError("Owned container removal did not complete")
        state = self.state()
        del state["containers"][role]
        self.save(state)

    def run(self, argv, *, timeout=30, check=True):
        if not 0 < timeout <= 1800:
            raise ValueError("command timeout must be 0..1800 seconds")
        argv = [str(value) for value in argv]
        print("$", shlex.join(argv), flush=True)
        log = self.work / "logs" / f"{time.time_ns()}.log"
        try:
            result = subprocess.run(argv, cwd=self.root, text=True, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            output = exc.stdout or b""
            log.write_text(output.decode(errors="replace") if isinstance(output, bytes) else output)
            raise RuntimeError(f"Deadline exceeded; no retry. Inspect {log}") from exc
        log.write_text(result.stdout)
        print(result.stdout[-12000:], end="" if result.stdout.endswith("\n") else "\n")
        if check and result.returncode:
            raise RuntimeError(f"Command exit {result.returncode}; inspect {log}")
        return result

    def step(self, label, enabled, action):
        if not enabled or os.environ.get("WORKSHOP_NOTEBOOK_MODE") == "validate":
            print(f"SKIPPED: {label}; explicit opt-in required (not live acceptance)")
            return None
        return action()
