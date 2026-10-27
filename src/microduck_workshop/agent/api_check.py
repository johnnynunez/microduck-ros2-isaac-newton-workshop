"""Admission of the exact public CASCADE revision and exercised extension APIs."""

import hashlib
import importlib.metadata
import inspect
import json
import subprocess
from pathlib import Path

from cascade.agent.llm import OpenAICompatClient
from cascade.agent.orchestrator import AgentOrchestrator
from cascade.agent.trace import TraceLogger
from cascade.memory.episodic import EpisodicMemory
from cascade.robotics.contracts import ResourceDescriptor, ToolDescriptor
from cascade.robotics.runtime import RobotRuntime

CASCADE_PIN = "d7a456c22d46d53e9588db6a55a0c6c916aa4963"
CLASSES = (
    ResourceDescriptor,
    ToolDescriptor,
    RobotRuntime,
    AgentOrchestrator,
    OpenAICompatClient,
    EpisodicMemory,
    TraceLogger,
)


def check_cascade_api():
    paths = {Path(inspect.getfile(cls)).resolve() for cls in CLASSES}
    runtime_path = Path(inspect.getfile(RobotRuntime)).resolve()
    root = runtime_path.parents[3]
    source_verified = False
    if (root / ".git").exists():
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        if head != CASCADE_PIN:
            raise RuntimeError("CASCADE checkout does not match the workshop pin")
        for path in paths:
            committed = subprocess.check_output(
                ["git", "-C", str(root), "show", f"{CASCADE_PIN}:{path.relative_to(root)}"]
            )
            if path.read_bytes() != committed:
                raise RuntimeError("CASCADE consumed source differs from pinned commit")
        source_verified = True
    else:
        provenance = importlib.metadata.distribution("cascade").read_text("direct_url.json")
        direct = json.loads(provenance or "{}")
        source_verified = (
            direct.get("vcs_info", {}).get("commit_id") == CASCADE_PIN
            and direct.get("url", "").removesuffix(".git")
            == "https://github.com/johnnynunez/cascade"
        )
    if not source_verified:
        raise RuntimeError("Cannot verify CASCADE origin; install requirements-agent.txt")
    required = {
        RobotRuntime: {"domains", "memory", "trace"},
        AgentOrchestrator: {"llm", "runtime", "max_steps", "decompose", "attach_images"},
        OpenAICompatClient: {"model", "base_url", "request_timeout_s", "max_retries", "extra_body"},
    }
    result = {}
    for cls in CLASSES:
        parameters = inspect.signature(cls).parameters
        if not required.get(cls, set()).issubset(parameters):
            raise RuntimeError(f"Unsupported CASCADE contract: {cls.__name__}")
        result[cls.__name__] = {
            name: (
                p.default
                if type(p.default) in {str, int, float, bool} or p.default is None
                else "required_or_factory"
            )
            for name, p in parameters.items()
        }
    return {
        "ok": True,
        "pin": CASCADE_PIN,
        "source_verified": source_verified,
        "classes": result,
        "source_sha256": {
            str(p.relative_to(runtime_path.parents[1])): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths
        },
    }


if __name__ == "__main__":
    print(json.dumps(check_cascade_api(), indent=2))
