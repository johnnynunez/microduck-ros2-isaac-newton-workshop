"""Explicit local brain + pinned CASCADE composition, without auto/hosted fallback."""

from __future__ import annotations

import argparse
import json
import signal
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

from cascade.agent.llm import OpenAICompatClient
from cascade.agent.orchestrator import AgentOrchestrator
from cascade.agent.trace import TraceLogger
from cascade.memory.episodic import EpisodicMemory
from cascade.robotics.runtime import RobotRuntime

from .domain import MicroduckDomain
from .gateway import RclpyGateway

CASCADE_PIN = "d7a456c22d46d53e9588db6a55a0c6c916aa4963"
MODEL_IDS = {"nemotron-3.5-bolt", "qwen3.8-27b", "Qwen/Qwen3.8-27B"}
TASK = (
    "Play the signal game using only onboard detections. Observe first. "
    "Only if tag 0 GO is visible and tag 1 STOP is absent, call microduck.step_forward "
    "once for the fixed step-forward-v1 maneuver: peak .10 m/s, 1s drive then 1s zero "
    "inside a 2s horizon. Choose no numeric parameters. Query verification. "
    "If the signal is absent, stale or STOP, do not move. Report failure unless "
    "the physical movement was independently verified. Never retry a motion."
)
PROMPT = """
This is the simulation-only MicroDuck signal lesson. Goals come ONLY from microduck.observe,
which represents Isaac ROS processing the onboard camera. Tag 0 means GO; tag 1 means STOP.
microduck.observe accepts {} or {"action":"observe"}; microduck.verify accepts {} or
{"action":"verify"}. These optional read selectors never authorize motion.
microduck.step_forward accepts {} or {"action":"step_forward"}; no numeric choices.
It invokes step-forward-v1, peak .10 m/s, 1s drive then 1s zero in a 2s horizon.
Use no other keys. A verified standstill/turn/legacy command cannot fulfill this step objective.
STOP wins, and absent, foreign or stale observations mean no movement. First observe; then
at most ONE short permitted forward action; then verify; then task_done. No coordinate goals,
map, world/root pose, external view, or invented detections. Bounds are enforced, not clipped.
accepted/executing/completed/verified are different. A stop ACK is not proof of rest.
If verification is unavailable or false, task_done(success=false) and explain that outcome.
Synthetic fixture data is only a model/tool diagnostic, never proof of perception or motion.
Do not reset stops, retry commands, or claim a successful walk from a service ACK.
"""


def local_endpoint(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/v1"
        or parsed.query
        or parsed.fragment
        or parsed.port is None
    ):
        raise ValueError("explicit loopback http://host:port/v1 endpoint required")
    return url


# Tool JSON is allowlisted again at the provider boundary. CASCADE's agent_tool_output
# only bounds size and MUST NOT be mistaken for a truth filter.
SCALARS = {
    "ok",
    "fresh",
    "episode_id",
    "request_id",
    "generation",
    "frame_sequence",
    "sim_time",
    "age_s",
    "frame_id",
    "signal",
    "reason",
    "accepted",
    "known",
    "completed",
    "verification_available",
    "verified",
    "status",
    "execution_ok",
    "delivery_uncertain",
    "latched",
    "physical_stop_verified",
    "pending",
    "task_complete",
    "success",
}


def project_tool_message(raw):
    if not isinstance(raw, dict):
        return {"ok": False, "reason": "invalid_tool_message"}
    result = {k: v for k, v in raw.items() if k in SCALARS and type(v) in {str, bool, int, float}}
    if "error" in raw:
        result["reason"] = "runtime_refused"
    if isinstance(raw.get("tag_ids"), list):
        result["tag_ids"] = [v for v in raw["tag_ids"] if type(v) is int]
    if isinstance(raw.get("postcondition"), dict):
        status = raw["postcondition"].get("status")
        result["postcondition"] = {
            "status": status if status in {"confirmed", "refuted", "unverified"} else "unverified"
        }
    if isinstance(raw.get("domains"), dict):
        result["domains"] = {"microduck": project_tool_message(raw["domains"].get("microduck", {}))}
    if isinstance(raw.get("domain_result"), dict):
        result["domain_result"] = project_tool_message(raw["domain_result"])
    return result


class RecordedLocalClient(OpenAICompatClient):
    """Logs provider API request parameters/responses, never HTTP auth headers.

    Override the pinned client's parameter-fallback hook to enforce one HTTP request
    per turn, no retry (including semantic retries), and a hard request count.
    """

    def __init__(self, *, model, base_url, transcript, max_requests=6, timeout_s=60):
        if model not in MODEL_IDS:
            raise ValueError("choose explicit local Nemotron 3.5 Bolt or Qwen3.8")
        if type(max_requests) is not int or not 1 <= max_requests <= 12:
            raise ValueError("request budget must be 1..12")
        super().__init__(
            model=model,
            base_url=local_endpoint(base_url),
            api_key="local-no-secret",
            supports_vision=False,
            temperature=0.0,
            request_timeout_s=timeout_s,
            max_retries=0,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        import httpx

        original = self._client
        self._client = original.with_options(
            http_client=httpx.Client(trust_env=False, follow_redirects=False),
            timeout=timeout_s,
            max_retries=0,
        )
        original.close()
        self.transcript = Path(transcript)
        self.transcript.parent.mkdir(parents=True, exist_ok=True)
        self.max_requests = max_requests
        self.requests = 0

    def _record(self, data):
        with self.transcript.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(data, allow_nan=False) + "\n")

    def chat(self, system, messages, tools=None, max_tokens=1024):
        clean = []
        for message in messages:
            role = message["role"]
            if role not in {"user", "assistant", "tool"}:
                raise ValueError("unexpected model-message role")
            item = {"role": role, "content": message["content"]}
            if role == "tool":
                item.update(
                    tool_call_id=message.get("tool_call_id", "call_0"),
                    content=json.dumps(
                        project_tool_message(json.loads(message["content"])), allow_nan=False
                    ),
                )
            elif role == "assistant" and "tool_calls" in message:
                item["tool_calls"] = message["tool_calls"]
            clean.append(item)
        return super().chat(system, clean, tools, max_tokens=min(1024, max_tokens))

    def _call_with_param_fallback(self, kwargs):
        if self.requests >= self.max_requests:
            raise RuntimeError("local model request budget exhausted")
        self.requests += 1
        if kwargs.get("tools"):
            # Require a schema-constrained call; the MODEL still chooses which tool and arguments.
            # task_done provides the completion/refusal channel. Never repair model arguments.
            kwargs["tool_choice"] = "required"
        self._record({"kind": "request", "index": self.requests, "body": kwargs})
        try:
            response = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            self._record(
                {"kind": "error", "index": self.requests, "error_type": type(exc).__name__}
            )
            raise
        self._record(
            {"kind": "response", "index": self.requests, "body": response.model_dump(mode="json")}
        )
        return response


class CapstoneRuntime(RobotRuntime):
    """An empty action ledger cannot prove the requested physical signal-game action."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._step_attempts = {}
        self._verdicts_in_flight = 0
        self._refuted_steps = set()

    def _execute(self, name, args=None, **kwargs):
        # Use the pinned dispatch hook so refutations are retained even if trace
        # recording fails. Never call upstream while holding its non-reentrant gate.
        tracks_verdict = name in ("microduck.step_forward", "microduck.verify")
        with self._gate:
            task_id = self._task_id
            if name == "microduck.step_forward":
                # Pre-dispatch refusals create upstream debt but no history row.
                self._step_attempts[task_id] = self._step_attempts.get(task_id, 0) + 1
            if tracks_verdict:
                self._verdicts_in_flight += 1
        result = None
        try:
            result = super()._execute(name, args, **kwargs)
            return result
        finally:
            if tracks_verdict:
                with self._gate:
                    if result and result.get("postcondition", {}).get("status") == "refuted":
                        # Bind to the actual receipt, not the task at wrapper
                        # entry: begin_task may race before upstream admission.
                        self._refuted_steps.add(
                            tuple(result.get(k) for k in ("episode_id", "request_id", "generation"))
                        )
                    self._verdicts_in_flight -= 1

    def unverified_actions(self):
        # The pinned CASCADE ledger conservatively retains the motion's initial
        # outcome. A later read can resolve ONLY that exact pending step; preserve
        # the original history and every unrelated/failed/stopped action debt.
        with self._gate:
            # Snapshot the pinned runtime's debt under its non-reentrant gate;
            # super().unverified_actions() would acquire that same gate again.
            missing = sorted(self._unverified | ({"robot stopped"} if self._latched else set()))
            domain = self.domains["microduck"]
            proof = domain._last_status or {}
            proof_key = tuple(proof.get(k) for k in ("episode_id", "request_id", "generation"))
            confirmed = (
                domain.forward_step_confirmed
                and proof_key not in self._refuted_steps
                and not self._verdicts_in_flight
            )
            records = [
                record
                for record in self._history
                if record["task_id"] == self._task_id and record["tool"] == "microduck.step_forward"
            ]
            witnessed = False
            if (
                confirmed
                and not self._latched
                and not self._closed
                and self._step_attempts.get(self._task_id, 0) == 1
                and len(records) == 1
            ):
                record = records[0]
                initial = record["result"]
                bound = all(
                    initial.get(key) == proof.get(key)
                    for key in ("episode_id", "request_id", "generation")
                )
                pending = (
                    initial.get("verification_available") is False
                    and initial.get("verified") is False
                    and initial.get("postcondition", {}).get("status") == "unverified"
                    and initial.get("status") in {"accepted", "executing", "completed"}
                )
                initially_confirmed = (
                    initial.get("verification_available") is True
                    and initial.get("verified") is True
                    and initial.get("postcondition", {}).get("status") == "confirmed"
                    and initial.get("status") in {"completed", "verified"}
                )
                witnessed = (
                    record["synthetic"] is False
                    and initial.get("accepted") is True
                    and initial.get("known") is True
                    and initial.get("delivery_uncertain") is not True
                    and bound
                    and (pending or initially_confirmed)
                )
                if witnessed and pending:
                    missing = [name for name in missing if name != "microduck.step_forward"]
            # A domain can retain an incomplete previous-task command. Even an
            # empty upstream ledger therefore requires a current-task witness.
            if not witnessed:
                missing.append("forward_step_objective_not_independently_verified")
            return missing


def build_agent(
    llm,
    gateway,
    run_dir,
    *,
    episode_id,
    frame_id,
    max_steps=6,
    observation_handler=None,
    motion_handler=None,
):
    if type(max_steps) is not int or not 1 <= max_steps <= 12:
        raise ValueError("step budget must be 1..12")
    kwargs = {} if observation_handler is None else {"observation_handler": observation_handler}
    domain = MicroduckDomain(
        gateway, episode_id=episode_id, frame_id=frame_id, motion_handler=motion_handler, **kwargs
    )
    runtime = CapstoneRuntime(
        {"microduck": domain}, memory=EpisodicMemory(), trace=TraceLogger(run_dir)
    )
    runtime.system_prompt += PROMPT
    runtime.tool_specs = [s for s in runtime.tool_specs if s["name"] != "list_resources"]
    agent = AgentOrchestrator(
        llm,
        runtime,
        max_steps=max_steps,
        decompose=False,
        attach_images=False,
        verify_milestones=False,
    )
    return agent, runtime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", choices=sorted(MODEL_IDS), default="qwen3.8-27b")
    parser.add_argument(
        "--episode-id", required=True, help="exact instructor-observed simulator episode"
    )
    parser.add_argument("--frame-id", required=True, help="exact onboard camera optical frame")
    parser.add_argument("--namespace", default="/workshop/microduck")
    parser.add_argument("--run-dir", type=Path, required=True, help="new output directory")
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--task", default=TASK)
    parser.add_argument(
        "--policy-manifest", type=Path, help="bind provider receipts to this student"
    )
    parser.add_argument("--policy-admission", type=Path, help="required with student manifest")
    parser.add_argument("--native-health-url", default="http://127.0.0.1:8766/v1/health")
    parser.add_argument(
        "--tools-file", type=Path, help="explicit trusted student/reference tools.py"
    )
    args = parser.parse_args(argv)
    from .api_check import check_cascade_api

    check_cascade_api()
    policy_identity = None
    if (args.policy_manifest is None) != (args.policy_admission is None):
        raise ValueError("student manifest and exact-policy admission must be provided together")
    if args.policy_manifest is not None:
        from microduck_workshop.policy.identity import read_policy_identity

        policy_identity = read_policy_identity(
            args.policy_manifest,
            args.policy_admission,
            args.native_health_url,
            episode_id=args.episode_id,
        )
    handlers = {}
    if args.tools_file:
        import importlib.util

        spec = importlib.util.spec_from_file_location("workshop_capstone_tools", args.tools_file)
        if spec is None or spec.loader is None:
            raise ValueError("tools file is not a Python module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        handlers = dict(
            observation_handler=module.translate_observation, motion_handler=module.step_forward
        )
        if not all(callable(value) for value in handlers.values()):
            raise ValueError("tools file must supply both callable handlers")
    args.run_dir.mkdir(parents=True, exist_ok=False)
    if policy_identity is not None:
        (args.run_dir / "policy_identity.json").write_text(
            json.dumps(policy_identity, indent=2) + "\n"
        )
    llm = RecordedLocalClient(
        model=args.model,
        base_url=args.base_url,
        transcript=args.run_dir / "provider.jsonl",
        max_requests=args.max_steps,
    )
    gateway = RclpyGateway(namespace=args.namespace)
    if policy_identity is not None:
        llm._record({"kind": "selected_native_policy_identity", **policy_identity})
    agent, runtime = build_agent(
        llm,
        gateway,
        args.run_dir,
        episode_id=args.episode_id,
        frame_id=args.frame_id,
        max_steps=args.max_steps,
        **handlers,
    )
    runtime.trace.stamp(
        {
            "cascade_pin": CASCADE_PIN,
            "model": args.model,
            "namespace": args.namespace,
            "episode_id": args.episode_id,
            "physical_acceptance": "requires_independent_same_episode_evidence",
            "selected_policy_identity": policy_identity,
        }
    )
    cancel = threading.Event()

    def stop(_signum, _frame):
        cancel.set()
        runtime.request_stop()  # AgentOrchestrator.cancel() is arm-specific at this pin.

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        report = agent.run_task(args.task, cancel_event=cancel)
        payload = asdict(report)
        # Report is an agent assertion, NOT a replacement for physical acceptance artifacts.
        payload["evidence_scope"] = "agent_ROS_episode_requires_independent_audit"
        if policy_identity is not None:
            final_identity = read_policy_identity(
                args.policy_manifest,
                args.policy_admission,
                args.native_health_url,
                episode_id=args.episode_id,
            )
            if final_identity != policy_identity:
                raise ValueError("student policy identity changed during agent episode")
            payload["selected_policy_identity"] = final_identity
            llm._record({"kind": "final_native_policy_identity", **final_identity})
        (args.run_dir / "report.json").write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps(payload, indent=2))
        return 0 if report.success else 2
    finally:
        runtime.close()
        llm.close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
