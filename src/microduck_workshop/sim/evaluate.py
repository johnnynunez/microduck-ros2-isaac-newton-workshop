"""Independent GT evaluator. Outputs stay in evaluator artifacts, not agent tools."""

import numpy as np


def evaluate_motion(trace, command, status):
    """Verdict for a bounded request; caller retains numeric metrics privately."""
    if len(trace) < 2:
        return {"verified": False, "reason": "insufficient native samples", "metrics": {}}
    poses = np.asarray([row["root_pose"] for row in trace])
    velocities = np.asarray([row["root_velocity"] for row in trace])
    q = poses[:, 3:7]
    yaw = np.unwrap(
        np.arctan2(
            2 * (q[:, 3] * q[:, 2] + q[:, 0] * q[:, 1]), 1 - 2 * (q[:, 1] ** 2 + q[:, 2] ** 2)
        )
    )
    displacement = poses[-1, :2] - poses[0, :2]
    forward = float(displacement @ np.array([np.cos(yaw[0]), np.sin(yaw[0])]))
    turn = float(yaw[-1] - yaw[0])
    up = 1 - 2 * (q[:, 0] ** 2 + q[:, 1] ** 2)
    tail = [i for i, row in enumerate(trace) if row["sim_time"] >= trace[-1]["sim_time"] - 0.2]
    tail_speed = float(np.linalg.norm(velocities[tail, :2], axis=1).mean())
    tail_yaw_rate = float(np.abs(velocities[tail, 5]).mean())
    safe = bool(np.isfinite(poses).all() and poses[:, 2].min() > 0.07 and up.min() > 0.7)
    elapsed = trace[-1]["sim_time"] - trace[0]["sim_time"]
    expected_forward, expected_turn = (
        command.vx * command.duration_s,
        command.wz * command.duration_s,
    )
    moved = (
        abs(forward) < 0.04
        if abs(expected_forward) < 1e-6
        else 0.25 * abs(expected_forward)
        <= np.sign(expected_forward) * forward
        <= 1.75 * abs(expected_forward) + 0.01
    )
    turned = (
        abs(turn) < 0.15
        if abs(expected_turn) < 1e-6
        else 0.25 * abs(expected_turn)
        <= np.sign(expected_turn) * turn
        <= 1.75 * abs(expected_turn) + 0.05
    )
    verified = bool(
        status == "completed"
        and safe
        and elapsed >= command.duration_s
        and moved
        and turned
        and tail_speed < 0.04
        and tail_yaw_rate < 0.10
    )
    reason = (
        "native motion and rest checks passed"
        if verified
        else "request interrupted; motion not verified"
        if status != "completed"
        else "native motion or rest check failed"
    )
    return {
        "verified": verified,
        "reason": reason,
        "metrics": {
            "forward_displacement_m": forward,
            "yaw_delta_rad": turn,
            "tail_speed_m_s": tail_speed,
            "tail_yaw_rate_rad_s": tail_yaw_rate,
            "elapsed_sim_s": elapsed,
            "safe": safe,
        },
    }


class MotionVerifier:
    """Private evaluator trace collector. HTTP receives only boolean/reason verdicts."""

    def __init__(self, owner, output):
        self.owner = owner
        self.output = output
        self.requests = {}

    def begin_tick(self, sim_time, truth):
        with self.owner.lock:
            pending = self.owner._pending
            if pending is not None and pending.command.request_id not in self.requests:
                self.requests[pending.command.request_id] = {
                    "command": pending.command,
                    "trace": [dict(sim_time=sim_time, **truth)],
                    "finished_at": None,
                }

    def end_tick(self, sim_time, truth):
        for request_id, record in list(self.requests.items()):
            record["trace"].append(dict(sim_time=sim_time, **truth))
            status = self.owner.status(request_id)
            if not status["completed"]:
                continue
            if record["finished_at"] is None:
                record["finished_at"] = sim_time
            if sim_time - record["finished_at"] < 0.35:
                continue
            verdict = evaluate_motion(record["trace"], record["command"], status["status"])
            self.owner.verdict(request_id, verified=verdict["verified"], reason=verdict["reason"])
            import json

            self.output.write(
                json.dumps(dict(request_id=request_id, **verdict), allow_nan=False) + "\n"
            )
            self.output.flush()
            del self.requests[request_id]


def evaluate_trace(trace):
    segments = {}
    for phase in sorted({row["phase"] for row in trace}):
        rows = [row for row in trace if row["phase"] == phase]
        poses = np.array([row["root_pose"] for row in rows])
        vels = np.array([row["root_velocity"] for row in rows])
        upright = 1 - 2 * (poses[:, 3] ** 2 + poses[:, 4] ** 2)
        end_time = rows[-1]["sim_time"]
        tail = [i for i, row in enumerate(rows) if row["sim_time"] >= end_time - 0.5]
        segments[phase] = {
            "samples": len(rows),
            "duration_s": end_time - rows[0]["sim_time"],
            "forward_displacement_m": float(poses[-1, 0] - poses[0, 0]),
            "planar_displacement_m": float(np.linalg.norm(poses[-1, :2] - poses[0, :2])),
            "min_root_height_m": float(poses[:, 2].min()),
            "min_up_cosine": float(upright.min()),
            "tail_mean_planar_speed_m_s": float(np.linalg.norm(vels[tail, :2], axis=1).mean()),
            "safe": bool(
                np.isfinite(poses).all() and poses[:, 2].min() > 0.07 and upright.min() > 0.7
            ),
        }
    complete = all(name in segments for name in ("walk", "zero", "resume"))
    passed = complete and all(segment["safe"] for segment in segments.values())
    if complete:
        passed = passed and all(
            segments[name]["duration_s"] >= 1.9 and segments[name]["forward_displacement_m"] >= 0.03
            for name in ("walk", "resume")
        )
        passed = passed and segments["zero"]["duration_s"] >= 1.9
        passed = passed and segments["zero"]["tail_mean_planar_speed_m_s"] < 0.04
    return {
        "evidence_kind": "INDEPENDENT_NATIVE_GT_EVALUATION",
        "segments": segments,
        "walk_stop_resume_verified": bool(passed),
        "thresholds": {
            "min_height_m": 0.07,
            "min_up_cosine": 0.7,
            "min_forward_displacement_m": 0.03,
            "max_stop_speed_m_s": 0.04,
        },
        "note": "No reset between phases. A control ACK is never used as physical evidence.",
    }
