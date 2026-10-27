"""ROS 2 Lyrical service client; imports ROS only when explicitly constructed."""

from __future__ import annotations

import os
import re
import threading
import time

FIELDS = {
    "observe": (
        "fresh",
        "episode_id",
        "generation",
        "frame_sequence",
        "sim_time",
        "age_s",
        "frame_id",
        "tag_ids",
        "reason",
    ),
    "bounded_motion": ("accepted", "episode_id", "request_id", "generation", "status", "reason"),
    "step_forward": ("accepted", "episode_id", "request_id", "generation", "status", "reason"),
    "motion_status": (
        "known",
        "completed",
        "verification_available",
        "verified",
        "status",
        "reason",
        "generation",
    ),
    "emergency_stop": ("success", "message"),
}


def service_request(request_type, fields):
    # Validate before ABI coercion: bool/string/nonfinite numbers remain invalid.
    # Lyrical's generated C float64 conversion requires PyFloat_Check, not int.
    motion_fields = {"vx", "vy", "wz", "duration_s"}
    if motion_fields.intersection(fields):
        from microduck_workshop.contracts import MotionCommand

        fields = MotionCommand.from_dict(fields).as_dict()
    request = request_type()
    for name, value in fields.items():
        setattr(request, name, float(value) if name in motion_fields else value)
    return request


def service_response(response, service):
    result = {name: getattr(response, name) for name in FIELDS[service]}
    if service == "observe":
        result["tag_ids"] = list(result["tag_ids"])
    return result


class RclpyGateway:
    """Separate stop node/executor: a blocked ordinary request cannot own its lane.

    The gateway owns the policy lease. This client never speaks the simulator HTTP API,
    never renews a lease, never retries motion, and never clears an emergency stop.
    """

    synthetic = False

    def __init__(self, *, namespace="/workshop/microduck", timeout_s=0.4):
        if not re.fullmatch(r"/workshop/[A-Za-z][A-Za-z0-9_/]*", namespace) or "//" in namespace:
            raise ValueError("use an explicit /workshop/... simulation namespace")
        if not 0 < timeout_s <= 2:
            raise ValueError("service timeout must be in (0, 2] seconds")
        import rclpy
        from microduck_workshop_interfaces.srv import BoundedMotion, MotionStatus, Observe
        from rclpy.context import Context
        from rclpy.executors import SingleThreadedExecutor
        from std_srvs.srv import Trigger

        domain_id = int(os.environ.get("ROS_DOMAIN_ID", "0"))
        if not 0 <= domain_id <= 232:
            raise ValueError("workshop ROS_DOMAIN_ID must be in 0..232")
        self.command_endpoint = f"ros2:domain:{domain_id}:{namespace.lstrip('/')}/step_forward"
        self._rclpy = rclpy
        self._context = Context()
        rclpy.init(context=self._context)
        self.timeout_s = timeout_s
        self._closed = False
        self._types = dict(
            observe=Observe,
            bounded_motion=BoundedMotion,
            step_forward=BoundedMotion,
            motion_status=MotionStatus,
            emergency_stop=Trigger,
        )
        self._nodes = [
            rclpy.create_node(
                "cascade_microduck_client", namespace=namespace, context=self._context
            ),
            rclpy.create_node("cascade_microduck_stop", namespace=namespace, context=self._context),
        ]
        self._clients = {
            name: self._nodes[int(name == "emergency_stop")].create_client(kind, name)
            for name, kind in self._types.items()
        }
        self._executors = [SingleThreadedExecutor(context=self._context) for _ in self._nodes]
        self._threads = []
        for node, executor in zip(self._nodes, self._executors):
            executor.add_node(node)
            thread = threading.Thread(target=executor.spin, daemon=True, name=node.get_name())
            thread.start()
            self._threads.append(thread)

    def _call(self, name, fields, *, deadline_monotonic_s=None):
        if self._closed:
            raise RuntimeError("ROS client closed")
        client = self._clients[name]
        deadline = time.monotonic() + self.timeout_s
        if not client.wait_for_service(timeout_sec=self.timeout_s):
            raise TimeoutError("ROS service unavailable")
        request = service_request(self._types[name].Request, fields)
        if deadline_monotonic_s is not None and time.monotonic() >= deadline_monotonic_s:
            raise TimeoutError("sensor freshness expired before ROS send")
        future = client.call_async(request)
        done = threading.Event()
        future.add_done_callback(lambda _: done.set())
        if not done.wait(max(0, deadline - time.monotonic())):
            # Cancelling this local future is NOT cancellation of a possibly delivered command.
            future.cancel()
            raise TimeoutError("ROS request uncertain; no retry")
        response = future.result()
        if response is None:
            raise RuntimeError("ROS service returned no response")
        return service_response(response, name)

    def observe(self):
        return self._call("observe", {})

    def bounded_motion(self, command, *, deadline_monotonic_s):
        return self._call(
            "bounded_motion", command.as_dict(), deadline_monotonic_s=deadline_monotonic_s
        )

    def step_forward(self, command, *, deadline_monotonic_s):
        return self._call(
            "step_forward", command.as_dict(), deadline_monotonic_s=deadline_monotonic_s
        )

    def motion_status(self, episode_id, request_id):
        return self._call("motion_status", dict(episode_id=episode_id, request_id=request_id))

    def emergency_stop(self):
        return self._call("emergency_stop", {})

    def close(self):
        if self._closed:
            return
        self._closed = True
        for executor in self._executors:
            executor.shutdown(timeout_sec=1.0)
        for thread in self._threads:
            thread.join(timeout=1.0)
        for node in self._nodes:
            node.destroy_node()
        self._context.shutdown()
