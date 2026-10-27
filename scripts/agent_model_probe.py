"""Real local-model diagnostic; synthetic read-only data, NEVER robot evidence."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from microduck_workshop.agent.runner import RecordedLocalClient, build_agent


class ReadOnlyDiagnostic:
    synthetic = True

    def observe(self):
        return dict(
            fresh=True,
            episode_id="model-diagnostic",
            generation=0,
            frame_sequence=1,
            sim_time=0.0,
            age_s=0.01,
            frame_id="diagnostic_camera",
            tag_ids=[1],
            reason="synthetic read-only fixture; not Isaac ROS",
        )

    def bounded_motion(self, command, *, deadline_monotonic_s):
        raise RuntimeError("No actuator exists in the model-only diagnostic")

    def motion_status(self, episode_id, request_id):
        return dict(
            known=False,
            completed=False,
            verification_available=False,
            verified=False,
            status="unknown",
            reason="no physical execution",
            generation=0,
        )

    def emergency_stop(self):
        return dict(success=True, message="No actuator exists")

    def close(self):
        pass


def valid_diagnostic(report):
    rows = report.tool_log
    return (
        not report.success
        and len(rows) == 3
        and [x["tool"] for x in rows] == ["microduck.observe", "microduck.verify", "task_done"]
        and rows[0]["args"] in ({}, {"action": "observe"})
        and rows[0]["result"].get("ok") is True
        and rows[0]["result"].get("signal") == "STOP"
        and rows[1]["args"] in ({}, {"action": "verify"})
        and rows[1]["result"].get("reason") == "no_command"
        and rows[2]["args"].get("success") is False
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:18510/v1")
    parser.add_argument("--model", default="qwen3.8-27b")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    llm = RecordedLocalClient(
        model=args.model,
        base_url=args.base_url,
        transcript=args.out / "provider.jsonl",
        max_requests=3,
    )
    agent, runtime = build_agent(
        llm,
        ReadOnlyDiagnostic(),
        args.out,
        episode_id="model-diagnostic",
        frame_id="diagnostic_camera",
        max_steps=3,
    )
    task = (
        "This is a model-only test with SYNTHETIC READ-ONLY DATA, no ROS or robot. "
        "Call microduck.observe, then microduck.verify to check whether any real command exists, "
        "then task_done with success=false explaining the actual evidence. Do not request motion."
    )
    try:
        report = agent.run_task(task)
        data = dict(
            evidence_scope="real_local_model_with_read_only_fixture_only",
            physical_success=False,
            ros_integration=False,
            model=args.model,
            provider_requests=llm.requests,
            report=asdict(report),
        )
        (args.out / "result.json").write_text(json.dumps(data, indent=2) + "\n")
        print(json.dumps(data, indent=2))
        return 0 if valid_diagnostic(report) else 2
    finally:
        runtime.close()
        llm.close()


if __name__ == "__main__":
    raise SystemExit(main())
