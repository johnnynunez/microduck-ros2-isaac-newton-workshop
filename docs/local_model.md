# Local Qwen3.8 with pinned CUDA llama.cpp

This route builds public upstream **llama.cpp** and downloads public **Qwen3.8-27B
UD-Q4_K_M GGUF**. It uses neither a hosted API nor native NVFP4 weights/KV. It is a
source-build route for **L40S (SM 8.9)** and **RTX PRO Blackwell (SM 12.0)**.
Compiling both architectures is not proof of execution on L40S or Brev.

## Immutable inputs and licenses

The machine-readable source of truth is [`provenance/local_model.json`](../provenance/local_model.json).

- llama.cpp: [`ggml-org/llama.cpp`, MIT](https://github.com/ggml-org/llama.cpp/tree/7aca0d2ea8d92b56911233b822db01f9fbb1ae50),
  commit `7aca0d2ea8d92b56911233b822db01f9fbb1ae50`.
- Quantizer/distributor: [`unsloth/Qwen3.8-27B-GGUF`](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/tree/4ca720788d1e01f1bff70c033e0d0028fd02e502),
  revision `4ca720788d1e01f1bff70c033e0d0028fd02e502`.
- File: `Qwen3.8-27B-UD-Q4_K_M.gguf`, 16,464,440,224 bytes;
  SHA-256 `322e194ff79741c7baa497c240f677f54b201b0efab44ca8e50f122b39123482`.
- The quantizer's pinned model card declares **Apache-2.0**, base model
  `Qwen/Qwen3.8-27B`. The [upstream license](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/LICENSE)
  is pinned separately. Retain applicable licenses and attribution if redistributing.
  No weights, model binaries or proprietary CUDA libraries are committed here.
- This is the current Qwen3.8 model, not an older Qwen substitute, fine-tuned
  derivative, fabricated model service or speculative drafter. No vision projector
  is downloaded: the capstone consumes the gateway's allowlisted sensor JSON.

## Prerequisites and resource envelope

Use Linux x86-64 with AVX2/FMA (the configured upstream CPU baseline), Python
**3.12**, CMake >=3.24, Ninja, a C/C++ compiler supported
by your toolkit, curl with `--retry-all-errors`, NVIDIA drivers and **CUDA Toolkit
>=12.8** (both SM 89 and 120 compilation). The scripts do not install packages,
change drivers or alter an existing service. Use your pre-provisioned Brev image
and confirm `nvidia-smi`, `cmake --version`, and `nvcc --version` first. If nvcc is
not on PATH, set `CUDACXX` to its absolute executable path; `/usr/local/cuda/bin/nvcc`
is detected automatically. Build on the destination: do not copy a CUDA 13.4 binary
onto a host with an incompatible driver/runtime.

Budget at least 30 GB disk for weights/source/build, 32 GiB host memory for the
bounded build/server job, and **24 GiB free VRAM before launch**. Build parallelism
is 1–8 jobs (default 8); GPU context is 4096 tokens, one concurrent sequence, 1024
output-token default, 256-token logical / 128-token physical batches, eight CPU
threads. KV is explicitly F16. Context shifting and automatic memory fitting are
disabled: failed limits must not silently change the experiment.

On a single 48 GB L40S, **finish training, export the policy, and stop the training
process before loading this model**. Start model inference, then the admitted
simulator and ROS workload; check the combined peak during the actual camera and
motion episode. Do not assume that training + simulator + Isaac ROS + inference
fits at once. The startup VRAM check is a preflight, not a GPU reservation or hard
allocator cap. A fresh hardware rehearsal remains necessary.

## Setup (before class)

All commands below run from this repository's root. They do not provision a paid
instance. Default cache: ignored `.workshop/model-cache`; override `MODEL_CACHE`
consistently on setup/start/stop if storage is elsewhere.

```bash
bash scripts/model_setup.sh --plan
# Foreground, or wrap in your site's memory-capped job manager:
bash scripts/model_setup.sh
bash scripts/model_setup.sh --verify-only
```

For a systemd user session, keep heavy work outside the interactive agent's scope:

```bash
systemd-run --user --wait --pipe --collect --unit=workshop-model-setup \
  -p MemoryMax=32G -p MemorySwapMax=0 -p TasksMax=512 \
  --working-directory="$PWD" bash "$PWD/scripts/model_setup.sh"
```

An equivalent site-specific cgroup/job wrapper is acceptable. On the validation
workstation the wrapper is `heavyrun -n roscon-model-setup -m 32G -- bash
scripts/model_setup.sh`. Do not install that workstation-only helper on Brev.
If there is no user systemd session, use the instructor's existing memory-capped
job/container environment rather than starting an unbounded background job.

`--build-only` and `--download-only` split staging. Setup takes an exclusive cache
lock. HTTPS downloads resume into `.partial` files, have bounded retries/timeouts,
and are renamed only after SHA-256 verification. A corrupt final artifact fails
closed and is preserved for inspection, never silently replaced. `--verify-only`
is offline and verifies source archive, GGUF and compiled binary/library hashes.
It is not a build, tool-calling or physical acceptance test.

The build passes `CMAKE_CUDA_ARCHITECTURES=89;120`, `GGML_NATIVE=OFF`. This upstream
revision translates 120 to **120a** for architecture-specific Blackwell kernels;
SM 89 kernels remain in the same library. Both CPU portability and CUDA architecture
selection are explicit. The tarball build stamps the pinned commit explicitly so
it cannot accidentally report the enclosing workshop repository's Git revision.
Prebuilt Web UI download/build and HTTPS support inside the server are disabled;
all model downloads are explicit setup operations, not runtime fallback.

## Start and stop

The server runs in the foreground under a supervisor, binds **127.0.0.1 only**, and
requires no secret. Port **18511** intentionally does not replace the separately
running vLLM server on 18510. This is the **standalone model recipe**; the unified
Brev/classroom recipe uses `MODEL_PORT=8080` explicitly on both model startup and
`brev_start.sh`. Do not mix the standalone 18511 endpoint with a client expecting
8080. `MODEL_GPU` selects one physical index or UUID (default
`CUDA_VISIBLE_DEVICES` if set, otherwise 0); multiple GPUs are refused.

```bash
MODEL_GPU=0 bash scripts/model_start.sh --plan
systemd-run --user --collect --unit=workshop-local-model \
  -p MemoryMax=32G -p MemorySwapMax=0 -p TasksMax=512 \
  --working-directory="$PWD" \
  env MODEL_GPU=0 bash "$PWD/scripts/model_start.sh"
curl --fail http://127.0.0.1:18511/health
curl --fail http://127.0.0.1:18511/v1/models
# Stop only this cache's exact recorded process; verify its exit:
bash scripts/model_stop.sh
```

For interactive supervised use, `MODEL_GPU=0 bash scripts/model_start.sh` stays
attached; Ctrl-C terminates its child. A production/session wrapper should enforce
the 32 GiB host cap shown above. `MODEL_PORT` may be 1024–65535, `MODEL_CONTEXT` may
be 1024–4096. Neither public binding nor multi-sequence execution is configurable.
Keep the loopback endpoint local; use approved SSH forwarding when needed, not a
public listener.

Startup checks artifact hashes and available VRAM, refuses occupied ports, and
waits up to 240 seconds for health. It logs to `.workshop/model-cache/run/server.log`.
Inherited `LLAMA_*` environment options are removed so they cannot change the bound
host or silently supply an API key. Stop uses Linux pidfds plus executable and
process-start identity; it never kills by name, port or a broad process pattern.
A stale/mismatched process record fails closed. No existing vLLM unit is managed.

## Genuine CASCADE tool-calling check

Use the actual pinned CASCADE environment described in [capstone.md](capstone.md),
not the bare simulator environment. The workshop pins CASCADE
`d7a456c22d46d53e9588db6a55a0c6c916aa4963`.

```bash
python -m microduck_workshop.agent.api_check
python scripts/agent_model_probe.py \
  --base-url http://127.0.0.1:18511/v1 --model qwen3.8-27b \
  --out runs/llamacpp-model-only-001
# Optional repeatable live pytest, in the same CASCADE environment:
MODEL_LIVE_TEST=1 PYTHONPATH=src python -m pytest tests/test_model_live.py -q
# No downloads/inference in the normal lifecycle unit tests:
python -m pytest tests/test_model_scripts.py -q
```

The unchanged `RecordedLocalClient`, `AgentOrchestrator`, `CapstoneRuntime` and
`MicroduckDomain` choose and execute the diagnostic's real tool calls. The model
must choose observe, receive a **synthetic STOP**, choose verify, receive
`no_command`, then choose `task_done(success=false)`. `tool_choice=required` asks
the model for a structured call; it does not prescribe its chosen tool/arguments.
The actual provider request and response objects are retained in `provider.jsonl`.
No parameter repair, scripted LLM, hosted fallback or fabricated answer is used.

**Exit 0 here means the model-only diagnostic passed. It does not mean a robot
walked or stopped.** No ROS graph, camera, Isaac ROS perception, learned policy or
Newton physical acceptance is exercised by this probe. The live capstone still
requires the complete same-episode evidence in `docs/capstone.md`; point that
runner at `http://127.0.0.1:18511/v1` only after its ROS prerequisites pass.

## Validation status

See the machine-readable validation section in `provenance/local_model.json`.
Local source compilation, bootstrap, real inference and stop/restart were exercised
on RTX PRO 6000 Blackwell, CUDA 13.4.92, GCC 11.5.0 and CMake 4.2.3. The release
validation passed **81 CPU agent/lifecycle tests and 2 live tests**. Two release
probe runs made **six real provider requests/responses**, each choosing
`observe(action=observe) → verify(action=verify) → task_done(success=false)` after
synthetic STOP / `no_command` results. Their provider transcript hashes are in the
manifest. The [portable provider/result evidence](../tests/test_model_release_evidence.json)
contains the unchanged SDK objects and orchestrator reports from both release runs;
original JSONL files and operational logs also remain in the private `.workshop` directory.

The actual llama-server process used **15,780 MiB VRAM**. The capped combined
release rebuild/start/probe/stop job reported **2.2G peak host memory**; this is a
local measurement, not a universal bound or a full simulator/ROS peak. Stop verified
the exact process exit, the owned port closed, and existing vLLM port 18510 remained
healthy. No motion or perception gate was relaxed and no agent source was changed.

`cuobjdump --list-elf` confirmed **sm_89 and sm_120a** code in the built CUDA library.
The main binary reports the full pinned source commit. The upstream GGML subproject
unconditionally re-runs Git discovery; `GIT_CEILING_DIRECTORIES` prevents discovery
of the enclosing repository, so its separate commit metadata honestly says
`unknown` for this verified tarball build. No source patch or fake Git history is
used. Stale downloaded UI assets are removed before building; zero UI assets are
embedded. Neither an L40S GPU nor a Brev VM was available for this lane's validation;
those are explicitly unverified deployment targets, not advertised hardware successes.

Earlier Bolt/GGUF DNS failures and vLLM model-only attempts remain in the historical
capstone evidence. They are not rewritten into results for this route. A source
archive DNS timeout and an interrupted initial HTTP/2 weight transfer also occurred;
source retry recovered, and the downloader uses resumable HTTP/1.1 plus bounded
all-error retries. The validation download also required a bounded parallel range
recovery of the same pinned URL. Its exact Content-Range and lengths are checked,
and the entire assembled file must pass the pinned SHA-256 before admission.
This is network recovery, not a different model/source.
Actual inference results are recorded separately from these bootstrap failures;
a successfully built binary alone is not a model result.
