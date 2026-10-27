# Read-only MicroDuck browser preview

The preview is a **human observer**, not a robot-control interface. It shows the
human-only overview next to the onboard head RGB feed. The overview is never an
agent perception input. No policy, balancing, task completion, or safety verdict
is inferred from an image or the simulator's `ready` field.

## Start

Use the workshop's Python 3.12 environment with the package installed:

```bash
python -m microduck_workshop.preview \
  --upstream http://127.0.0.1:8766 --bind 127.0.0.1 --port 8765
```

Those are the defaults. Open `http://127.0.0.1:8765/`. The module needs only the
Python standard library; no Kit, ROS, agent SDK, Pillow, GPU, or browser framework
is imported by the server. The package contains the actual `web/index.html`,
`web/app.js`, and `web/style.css` assets. Fonts, CSS, and JavaScript require no CDN.

For Brev, expose **8765 only**, behind an authenticated Secure Link. If that proxy
requires a non-loopback listener, explicitly use `--bind 0.0.0.0`. This server has
no built-in authentication or TLS: an unrestricted public listener is not an
acceptable substitute for Secure Link. Keep the control service on loopback
**8766**, never a public endpoint. Run the preview and simulation in the same
host/network and monotonic-clock namespace. Deployment orchestration belongs to
the workshop launcher, not this module.

The browser retains same-origin authentication cookies for Secure Link. The
preview never forwards those cookies, authorization headers, lease headers,
request bodies, or any other browser-supplied header to the simulator. It never
reads or emits a robot lease token. Authentication at the real Brev boundary
still needs deployment acceptance; the browser test uses a labeled synthetic
cookie-auth boundary, not a real Brev session.

## Exact HTTP surface

Only these exact `GET` request targets are accepted. Queries, encoded aliases,
absolute URLs, traversal paths, and additional routes are rejected, not proxied.

| Preview route | Source |
| --- | --- |
| `/`, `/index.html` | Packaged HTML |
| `/app.js`, `/style.css` | Packaged offline assets |
| `/head.jpg` | Fixed `GET /v1/camera` |
| `/overview.jpg` | Fixed `GET /v1/overview` |
| `/status` | Fixed `GET /v1/health`, filtered |

Unknown routes return **404**. Non-GET methods, including POST, HEAD, OPTIONS,
CONNECT, and TRACE, return **405** with `Allow: GET`. No command, stop, claim,
renew, state, calibration, reset, file browsing, arbitrary proxy, or raw-control
route exists. A stop belongs to the separate authorized ROS/operator workflow;
there is intentionally no actuation button on this page.

`--upstream` accepts only the exact strings `http://127.0.0.1:8766` and
`http://localhost:8766` (without trailing slash). Both connect directly to literal
`127.0.0.1:8766`; there is no hostname resolution, redirect following, or use of
environment proxy settings. Upstream bodies are bounded to **64 KiB JSON** or
**8 MiB JPEG** with a **1 s total network deadline**, including slow-drip reads.
Malformed, oversized, timed-out, unavailable, or redirected upstream responses
produce a generic **503**, without upstream error details or private headers.

The status JSON contains **only**:

```
protocol_version, ready, physics, episode_id, generation, sim_time
```

The server validates their types, supported protocol/backend, ASCII epoch,
nonnegative finite numbers, and JavaScript-safe generation. It rejects duplicate
JSON keys and nonfinite JSON values, including exponent overflow. Runtime paths,
world poses, lease secrets, and other upstream fields are not exposed. The
browser renders metadata as text, not HTML. Responses use `Cache-Control:
no-store`, `nosniff`, and a restrictive same-origin Content Security Policy.

## Image provenance and freshness

The four atomic headers from [transport v1](transport.md) are validated and
preserved verbatim on both image routes:

- `X-Microduck-Episode`
- `X-Microduck-Sequence`
- `X-Microduck-Sim-Time`
- `X-Microduck-Capture-Monotonic`

The server adds `X-Preview-Age-S`, computed from same-host `time.monotonic()` minus
the **source capture** timestamp, and `X-Preview-State: fresh|stale`. Missing,
ambiguous, nonfinite, negative, or future capture provenance is rejected. JPEG
content type and envelope markers are checked; the browser must successfully
decode a new image before replacing its previous image. No synthetic image,
placeholder JPEG, renderer, interpolation, or server-side last-frame cache is
used. Before the source has a frame the image route returns 503.

The page displays each view's episode/epoch, sequence, simulation capture time,
and wall capture age. Age continues increasing while requests stall or fail;
receiving an old frame again does not reset its capture age. It conservatively
includes the entire browser request elapsed time in its age estimate.

- **LIVE**: decoded source capture age at most 0.5 s, a matching status episode,
  and a recent status reporting `ready: true`. This is not a renderer-FPS or task
  success claim.
- **STALE**: an old capture, epoch mismatch, or source not ready.
- **OFFLINE**: failed/missing image feed, or missing/failed status. The last
  decoded image may remain visible, but carries an `OFFLINE · LAST IMAGE` warning.
- **NO FRAME**: nothing has decoded yet; the viewport stays empty.

Status becomes unavailable after 1 s without a timely response. Retained runtime
values are not extrapolated. The UI polls each source independently at a target
**4 Hz**, skipping overlapping requests. This is **UI refresh, not renderer
FPS**. Overview and head images are independent captures, not frame-synchronous.

## Verification

CPU HTTP tests use an explicitly **synthetic upstream fixture**, redirected
internally to an ephemeral loopback port. They never bind 8766 or touch an
existing simulation. They exercise real HTTP requests, method/path refusal,
credential stripping, JSON validation, provenance, byte limits, timeouts,
redirect/proxy refusal, and the real CLI startup/shutdown path:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest tests/test_preview.py -q
```

Optional real-browser tests need Playwright, Pillow (for a labeled synthetic test
JPEG), and installed Google Chrome or Chromium. They test LIVE→STALE→OFFLINE,
independent feeds, epoch mismatch, failed status, Secure Link cookie handling,
and mobile overflow. They skip when those optional test tools are absent:

```bash
env -u PYTHONPATH .venv/bin/python -m pytest tests/test_preview_browser.py -q
```

For **visual-only** inspection of an already recorded actual head-camera JPEG:

```bash
env -u PYTHONPATH PREVIEW_RECORDED_JPEG=/absolute/path/to/head_camera.jpg \
  .venv/bin/python -m pytest tests/test_preview_browser.py::test_recorded_camera_visual_only_qa -q
```

That test labels its epoch `RECORDED_QA_NOT_LIVE`, sets the fixture to not-ready
and an old capture timestamp, and leaves overview empty. Fixture sequence,
simulation time, and age are deliberately synthetic QA metadata, not recovered
recording provenance. Screenshots land in `.workshop/preview-qa/`; neither the
source JPEG nor screenshots are committed. This test is **not live-camera,
physics, ROS, or task acceptance**. A real native episode and real Brev Secure
Link must still be accepted by the runtime/deployment owners.

Wheel acceptance should build and install the wheel into a fresh Python 3.12
environment, run `python -I -m microduck_workshop.preview --port 0` outside the
source tree, and fetch all four static routes. This catches missing package data
without relying on an editable installation. The current Hatch package layout
includes all three web assets without a packaging-file change.
