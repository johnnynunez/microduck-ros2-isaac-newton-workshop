# Local model evidence — NOT robot success

These artifacts contain actual local Qwen3.8-27B responses obtained through the real
pinned CASCADE `OpenAICompatClient` and `AgentOrchestrator`. The gateway was deliberately
synthetic and read-only; there was no ROS graph, camera, detector or actuator in these
runs. All physical-success and ROS-integration flags remain false.

- Model: `Inferact/Qwen3.8-27B-NVFP4`, revision `6128240ebaf4eaa7bad2b3d1c72c37d677c5f462`.
- CASCADE: `d7a456c22d46d53e9588db6a55a0c6c916aa4963` (MIT).
- Serving: existing vLLM 0.32.0, RTX PRO 6000 Blackwell (SM 12.0), NVFP4 KV,
  FLASHINFER, one sequence, 8192-token context, eager execution, thinking disabled.
- Model license: Apache-2.0 in the pinned model snapshot; no weights are included here.
- Scope: fifteen actual inference requests across five bounded attempts, three per attempt.
  This was schema-debugging plus a final committed-code smoke, not a performance benchmark.
  No motion call was executed. `model-probe-final` ran implementation commit
  `032c5415622d661ee9f8749f6b0571ae67ea080f`, including proxy/redirect hardening.

| Directory | Actual result |
|---|---|
| `model-probe` | Failed read dispatch: model supplied undeclared `action` arguments. The original probe's exit-0 check was too weak (names only); it was replaced by result/argument assertions. Do not count that exit code as a pass. |
| `model-probe-v2` | Explicit empty-argument prompting still produced `action: "{}"`; correctly refused. Exit 2. |
| `model-probe-v3` | `tool_choice=required` alone did not remove the invalid arguments. Exit 2. |
| `model-probe-v4` | Passed model-only diagnostic: declared constant read selectors; real model chose observe, received synthetic STOP, chose verify, received `no_command`, then honestly chose `task_done(success=false)`. Exit 0. |
| `model-probe-final` | Final committed-code smoke passed the same three-turn diagnostic with proxy environment ignored and redirects disabled. The model again reported no physical success. |

`provider.jsonl` contains the actual parameters passed to the OpenAI-compatible SDK and
its returned response objects. The `extra_body` dictionary is merged into HTTP JSON by
the SDK; these are not raw wire packets. No authentication headers are logged. `result.json`
is the actual orchestrator report, explicitly labeled synthetic/model-only. No historical
result was edited after its run. The optional read selectors do not change ROS service
schemas, enable motion, relax freshness/velocity limits, or synthesize a model answer.

The final task's false success field is the correct result: it performed no physical
movement. This evidence proves local model/tool integration only. Live perception,
learned Newton movement, physical expiry/stop, and execution on Brev remain separate gates.
