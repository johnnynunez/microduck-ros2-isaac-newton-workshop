# Live camera latency: payload, not a frozen renderer

## Change

`sim.play --cameras` now renders the onboard RGB camera at **320×240** by default.
Use `--head-camera-resolution 640x480` to explicitly select the original resolution.
Direct `MicroDuckRuntime` construction retains its 640×480 default for existing
native fixtures. The separately authored **human-only** overview stays 640×480.

This changes the authored render product, not a post-render resize. Camera position,
orientation, focal length, apertures, RGB encoding and JPEG quality are unchanged.
Calibration still comes from `camera.data.intrinsic_matrices`, not a hard-coded
scale applied to old intrinsics. Actual 320×240 readback was:

```text
K = [[240, 0, 160], [0, 240, 120], [0, 0, 1]]
frame_id = microduck_head_optical
```

Physics remains 0.005 s with four substeps/control tick. ONNX, BAM, zero/balance,
intent gates, 0.5 s freshness and 5 s verification timeout are unchanged. Camera
capture timestamps and sequence numbers are untouched; cached pixels are never
restamped. No model service or model batching configuration was changed.

## Measurement and root cause

The tests used the actual pinned Isaac Lab/Newton renderer, public Isaac ROS 5
cuAprilTag, and CASCADE calling the existing `qwen3.8-27b` llama.cpp endpoint on
port 18511. Simulator, CUDA detector and model shared physical GPU 1. The unrelated
vLLM server remained resident and untouched. Limits were Sim 32 GiB/8 CPUs,
ROS 24 GiB/8 CPUs, agent 4 GiB/2 CPUs; ROS/agent used private shared IPC.

Native timings, HTTP camera/state capture ages, ROS observe responses, and
independent camera-info/image/detection subscribers were recorded before, during
and after actual model invocation. All logs were retained **before** container
stop; final logs were saved separately before removal.

The original 640×480 render was not freezing for the freshness interval. In the
first baseline, maximum HTTP camera age during inference was 0.163 s, while only
41/75 ROS observations were fresh. The independent topic probe localized the
loss downstream of HTTP rendering: camera-info arrived regularly, but large RGB
images and detections were missing. Matched detector headers preserved the source
timestamp; matched delivery was usually milliseconds, not a long detector queue.

| Measured run | Head RGB | Camera-info / image / detector messages | Max detector gap | Fresh observations during model | Fresh age p95 / max during model |
|---|---|---|---|---|---|
| `topics` baseline | 640×480 | 321 / 157 / 151 | 2.001 s | 90 / 102 | 0.426 / 0.499 s |
| `lowpayload` | 320×240 | 322 / 322 / 322 | 0.266 s | 102 / 102 | 0.211 / 0.253 s |
| `confirm` | 320×240 | 326 / 326 / 326 | 0.311 s | 101 / 101 | 0.211 / 0.346 s |

Fresh-age statistics exclude stale responses, which intentionally expose no usable
capture. Message totals span each entire topic probe, not just the model interval.
Every monitored observation before and after the model was also fresh in both
320×240 runs. The uncompressed RGB payload is 230,400 rather than 921,600 bytes.
These are bounded observations, not a guarantee of future loss-free delivery.

The controlled resolution change removed the observed **large-image transport
loss**. This experiment does not identify a particular Fast DDS internal buffer
as the cause; no DDS, sysctl, driver, host package or global environment tuning
was performed. Renderer quality/threading/decimation changes were not stacked
on top of the measured fix.

## Remaining limitations — not physical success

Both lower-payload model runs observed real GO, submitted a real accepted step,
received `verified=false`, and reported failure. Freshness did not expire, but
fresh detections briefly contained no tag during motion. A retained HTTP image
near one such observation shows the board clipped at the top of the onboard
view. Its sequence is 1000 while the empty observation refers to 996: this is
nearby evidence, **not** the exact detector input. This change does not alter
optics or the authored board placement to conceal that separate issue.

The confirmation's independent native verdict reports an interrupted request,
0.0248023 m forward displacement over 0.8 simulated seconds, not a successful
maneuver. Full merged GO/STOP admission remains separate work.

Native physics is also slower than real time: in confirmation, `sim.step` averaged
12.54 ms during model invocation per 5 ms physics tick (10.89 ms after invocation).
Camera publication averaged 17.78 ms per control tick during inference. Thus
removing image loss does **not** establish that a full maneuver plus rest will
fit the unchanged verifier deadline. No physics optimization was attempted here.

## Evidence and regression checks

Local evidence is retained under
`.worktrees/camera-perf/.workshop/camperf/` relative to the main checkout:

- `baseline02/`, `topics/`, `lowpayload/`, `confirm/`: native timings, ROS/HTTP
  samples, actual model provider/trace/report files, original JPEGs, GPU placement,
  container limits/identity and pre-stop/final logs.
- `confirm/camera_info.json`: actual rendered-camera calibration.
- `confirm/empty-tags-camera-1000.{jpg,json}`: nearby clipped-frame evidence with
  distinct image and observation sequence IDs.
- `comparison.json`: programmatically aggregated receipt, including source hashes,
  exact sample counts, model exit events and native evaluation summaries.
- `configure.py`, `instrument.py`, `probe.py`, `topicprobe.py`, `run.sh`,
  `summarize.py`, `compare.py`: private bounded diagnostic harness. Do not run it
  concurrently with another simulator on port 8766. `run.sh` accepts a **new** run
  directory name and refuses to overwrite an existing directory.

The scene-authoring and CLI regressions in `tests/test_camera_latency.py` were
written and observed failing before implementation. Lightweight SDK stand-ins
cover dimensions/optics; they are not presented as rendered-camera evidence.
The native/ROS/model runs above supply that evidence.

Historical native step receipts bind the complete old `native.py` and `play.py`
files. Their current-source SHA test consequently fails after this source change.
Those historical hashes and receipts were deliberately **not rewritten**. A new
combined admission/provenance chain must describe the merged implementation;
passing the camera-latency experiment is not a replacement for that gate.
