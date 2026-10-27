"""Real CASCADE domain; all actuator IO goes through the ROS gateway interface."""

from __future__ import annotations

import threading
import time
import uuid

from cascade.robotics.contracts import ResourceDescriptor, ToolDescriptor

from microduck_workshop.contracts import (
    MAX_SENSOR_AGE_S,
    ContractError,
    MotionCommand,
    identifier,
)

from .observation import translate_observation

MOTION_KEYS = {"vx", "vy", "wz", "duration_s"}
STATUS_VALUES = {
    "accepted",
    "executing",
    "completed",
    "rejected",
    "stopped",
    "expired",
    "failed",
    "unknown",
    "verified",
    "cancelled",
}


def project_status(raw, *, request_id, episode_id, generation, synthetic):
    """No arbitrary reason strings, evidence dictionaries or world-state fields."""
    valid = (
        type(raw.get("generation")) is int
        and raw["generation"] == generation
        and type(raw.get("known")) is bool
        and type(raw.get("completed")) is bool
        and type(raw.get("verification_available")) is bool
        and type(raw.get("verified")) is bool
        and raw.get("status") in STATUS_VALUES
    )
    if not valid:
        return dict(
            ok=False,
            request_id=request_id,
            episode_id=episode_id,
            known=False,
            completed=False,
            verification_available=False,
            verified=False,
            status="unknown",
            reason="invalid_receipt",
            postcondition={"status": "unverified"},
        )
    known = raw["known"]
    completed = known and raw["completed"]
    available = completed and raw["verification_available"]
    verified = (
        available
        and raw["verified"]
        and not synthetic
        and raw["status"] in {"completed", "verified"}
    )
    verdict = (
        "confirmed"
        if verified
        else "refuted"
        if available and not raw["verified"]
        else "unverified"
    )
    return dict(
        ok=known,
        episode_id=episode_id,
        request_id=request_id,
        generation=generation,
        known=known,
        completed=completed,
        verification_available=available,
        verified=verified,
        status=raw["status"],
        reason="synthetic_not_physical_evidence" if synthetic else "gateway_verdict",
        postcondition={"status": verdict},
    )


class MicroduckDomain:
    """One command per task; stop is independent and uncertainty cannot be retried."""

    domain_id = "microduck"
    motion_skills = frozenset({"step_forward"})

    def __init__(
        self,
        gateway,
        *,
        episode_id,
        frame_id,
        verification_timeout_s=8.0,
        poll_interval_s=0.05,
        observation_handler=translate_observation,
        motion_handler=None,
    ):
        self.gateway = gateway
        self.episode_id = identifier(episode_id, "episode_id")
        if not isinstance(frame_id, str) or not frame_id or len(frame_id) > 128:
            raise ContractError("invalid expected camera frame")
        if not 0 < verification_timeout_s <= 8 or not 0 < poll_interval_s <= 0.2:
            raise ContractError("invalid verification budget")
        self.frame_id = frame_id
        self.verification_timeout_s = verification_timeout_s
        self.poll_interval_s = poll_interval_s
        self.observation_handler = observation_handler
        self.motion_handler = motion_handler
        self.synthetic = gateway.synthetic is not False
        self._stopped = threading.Event()
        self._operation = threading.Lock()
        self._closed = False
        self._attempted = False
        self._observed = None
        self._last = None
        self._last_status = None
        self._last_skill = None
        self._accepted = False
        self.resources = (
            ResourceDescriptor(
                "microduck.command",
                "mobile_base",
                "microduck",
                capabilities=("step-forward-v1",),
                controller_id=getattr(gateway, "command_endpoint", "ros2:fixture"),
                writer_id="microduck",
                synthetic=self.synthetic,
                admission="unvalidated",
                metadata={
                    "transport": "ROS2_services",
                    "simulation_only": True,
                    "perception": "onboard_camera_isaac_ros_apriltag",
                    "units": "body_frame_SI",
                },
            ),
        )

        def read_params(operation):
            return {
                "type": "object",
                "properties": {"action": {"type": "string", "enum": [operation]}},
                "required": [],
                "additionalProperties": False,
            }

        self.tool_descriptors = tuple(
            ToolDescriptor(
                name=f"microduck.{name}",
                description=description,
                parameters=schema,
                domain="microduck",
                local_name=name,
                effect=effect,
                requires=("microduck.command",),
                writes=("microduck.command",) if effect == "motion" else (),
            )
            for name, description, schema, effect in (
                (
                    "observe",
                    "Read fresh onboard Isaac ROS tag detections. Tag 0=GO; tag 1=STOP; STOP wins. No world pose.",
                    read_params("observe"),
                    "read",
                ),
                (
                    "step_forward",
                    "Request ONE fixed step-forward-v1 on fresh GO: peak .10 m/s, 1s drive then 1s zero, total 2s. No numeric choices or retries. ACK is not success.",
                    read_params("step_forward"),
                    "motion",
                ),
                (
                    "verify",
                    "Query the last command's independent verdict; no coordinates. Never infer verification from acceptance.",
                    read_params("verify"),
                    "read",
                ),
            )
        )
        self.tool_specs = [tool.as_spec() for tool in self.tool_descriptors]

    def _observation(self):
        started = time.monotonic()
        raw = self.gateway.observe()
        return self.observation_handler(
            raw,
            episode_id=self.episode_id,
            frame_id=self.frame_id,
            round_trip_s=time.monotonic() - started,
        )

    def execute(self, name, args):
        if not isinstance(args, dict):
            return {"ok": False, "reason": "invalid_arguments"}
        if name != "walk_bounded" and args and args != {"action": name}:
            return {"ok": False, "reason": "invalid_arguments"}
        if not self._operation.acquire(blocking=False):
            return {"ok": False, "reason": "operation_busy"}
        try:
            if self._closed:
                return {"ok": False, "reason": "domain_closed"}
            if name == "observe":
                self._observed = self._observation()
                return self._observed.copy()
            if name == "step_forward":
                if self.motion_handler is not None:
                    return self.motion_handler(self, args)
                return self.step_forward(args)
            if name == "walk_bounded":
                # Compatibility helper only; deliberately absent from the model catalog.
                return self.walk_bounded(args)
            if name == "verify":
                return self.verify()
            return {"ok": False, "reason": "unsupported_tool"}
        except Exception:
            # Transport exceptions can include raw payloads/URLs. Never echo them to the model.
            return {"ok": False, "reason": "gateway_or_handler_error"}
        finally:
            self._operation.release()

    def step_forward(self, args):
        if not isinstance(args, dict) or (args and args != {"action": "step_forward"}):
            return {"ok": False, "reason": "invalid_arguments"}
        return self._motion(dict(vx=.10, vy=0., wz=0., duration_s=2.), "step_forward")

    def walk_bounded(self, args):
        """Legacy diagnostic, never a witness for the independent forward-step goal."""
        return self._motion(args, "bounded_motion")

    def _motion(self, args, skill):
        if self._stopped.is_set() or self._attempted:
            return {"ok": False, "reason": "stopped_or_command_already_attempted"}
        if not isinstance(args, dict) or set(args) != MOTION_KEYS:
            return {"ok": False, "reason": "invalid_arguments"}
        # Validate the shared strict envelope before doing any sensor/actuator IO.
        MotionCommand(self.episode_id, "validation", 0, **args)
        before = self._observed
        if not before or before.get("signal") != "GO" or before.get("fresh") is not True:
            return {"ok": False, "reason": "observe_GO_first"}
        current = self._observation()  # AFTER model inference, immediately before admission.
        if (
            current.get("signal") != "GO"
            or current.get("fresh") is not True
            or current.get("generation") != before.get("generation")
            or current.get("frame_sequence", -1) < before.get("frame_sequence", 0)
            or current.get("sim_time", -1) < before.get("sim_time", 0)
        ):
            return {"ok": False, "reason": "perception_or_generation_changed"}
        if self._stopped.is_set():
            return {"ok": False, "reason": "stop_before_send"}
        command = MotionCommand(self.episode_id, uuid.uuid4().hex, current["generation"], **args)
        self._attempted = True  # Before IO: even uncertain sends consume this task's budget.
        self._last = command
        self._last_skill = skill
        self._accepted = False
        self._last_status = None
        try:
            ack = getattr(self.gateway, skill)(
                command, deadline_monotonic_s=time.monotonic() + MAX_SENSOR_AGE_S - current["age_s"]
            )
            if (
                type(ack.get("accepted")) is not bool
                or ack.get("episode_id") != command.episode_id
                or ack.get("request_id") != command.request_id
                or type(ack.get("generation")) is not int
            ):
                raise ValueError("unbound acknowledgement")
            if not ack["accepted"]:
                return {
                    "ok": False,
                    "accepted": False,
                    "request_id": command.request_id,
                    "status": "rejected",
                    "reason": "gateway_rejected",
                }
            if ack["generation"] != command.expected_generation + 1:
                raise ValueError("unexpected generation")
            self._accepted = True
        except Exception:
            self.stop()
            return {
                "ok": False,
                "accepted": None,
                "delivery_uncertain": True,
                "request_id": command.request_id,
                "reason": "uncertain_delivery_no_retry",
                "postcondition": {"status": "unverified"},
            }
        deadline = time.monotonic() + self.verification_timeout_s
        while True:
            status = self.verify()
            if self._stopped.is_set():
                return {
                    **status,
                    "ok": False,
                    "accepted": True,
                    "verified": False,
                    "postcondition": {"status": "unverified"},
                    "reason": "stopped",
                }
            if status.get("verification_available") or time.monotonic() >= deadline:
                return {**status, "accepted": True, "execution_ok": status.get("completed", False)}
            self._stopped.wait(min(self.poll_interval_s, max(0, deadline - time.monotonic())))

    def verify(self):
        command = self._last
        if command is None:
            return {"ok": False, "known": False, "verified": False, "reason": "no_command"}
        try:
            raw = self.gateway.motion_status(command.episode_id, command.request_id)
        except Exception:
            raw = {}
        status = project_status(
            raw,
            request_id=command.request_id,
            episode_id=command.episode_id,
            generation=command.expected_generation + 1,
            synthetic=self.synthetic,
        )
        self._last_status = status
        return status.copy()

    @property
    def physical_verdict_confirmed(self):
        return (
            not self.synthetic
            and not self._stopped.is_set()
            and (self._last_status or {}).get("verified") is True
        )

    @property
    def forward_step_confirmed(self):
        command = self._last
        return (
            self.physical_verdict_confirmed
            and self._accepted
            and self._last_skill == "step_forward"
            and command is not None
            and command.episode_id == self.episode_id
            and (command.vx, command.vy, command.wz, command.duration_s) == (.10, 0., 0., 2.)
        )

    def begin_task(self):
        # Never clear the stop latch. Unresolved delivery cannot be forgotten by a new task.
        if self._last is None or (self._last_status or {}).get("completed") is True:
            self._attempted = False
            self._last = None
            self._last_status = None
            self._last_skill = None
            self._accepted = False
        self._observed = None

    def stop(self):
        self._stopped.set()  # Does not wait for the ordinary operation lock.
        try:
            raw = self.gateway.emergency_stop()
            return {
                "ok": raw.get("success") is True,
                "latched": True,
                "physical_stop_verified": False,
            }
        except Exception:
            return {
                "ok": False,
                "latched": True,
                "reason": "stop_transport_error",
                "physical_stop_verified": False,
            }

    def reset_stop(self):
        return {"ok": False, "reason": "staff_reset_not_implemented_in_frozen_ROS_contract"}

    def close(self):
        if self._closed:
            return {"ok": True, "complete": True}
        stopped = self.stop()
        self.gateway.close()
        self._closed = True
        return {"ok": stopped["ok"], "complete": True, "physical_stop_verified": False}
