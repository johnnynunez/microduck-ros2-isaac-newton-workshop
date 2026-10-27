"use strict";

// The page is an observer, not an agent or a robot-control client.
const POLL_MS = 250; // UI refresh target, never a claim about renderer FPS.
const STALE_S = 0.5;
const STATUS_TIMEOUT_MS = 1000;
const runtime = { value: null, at: 0, failed: true, busy: false };
const feeds = ["overview", "head"].map(id => ({
  id, node: document.getElementById(id), frame: null, url: null, failed: true, busy: false
}));
const text = (node, selector, value) => { node.querySelector(selector).textContent = value; };
const seconds = value => `${value.toFixed(2)} s`;

function validNumber(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}
function validEpoch(value) {
  return typeof value === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(value);
}
function headerNumber(response, key) {
  const raw = response.headers.get(key);
  if (raw === null || raw.trim() === "" || !validNumber(Number(raw))) {
    throw new Error("Missing or invalid source provenance");
  }
  return Number(raw);
}
async function get(path, signal) {
  const response = await fetch(path, {
    // Secure Link may authenticate same-origin requests with its own cookie.
    // The Python boundary never forwards browser credentials to the simulator.
    method: "GET", cache: "no-store", credentials: "same-origin", redirect: "error", signal
  });
  if (!response.ok) throw new Error("Source unavailable");
  return response;
}

async function pollStatus() {
  if (runtime.busy) return;
  runtime.busy = true;
  const started = performance.now();
  try {
    const response = await get("/status", AbortSignal.timeout(1800));
    const value = await response.json();
    if (value.protocol_version !== 1 || typeof value.ready !== "boolean" ||
        value.physics !== "newton" || !validEpoch(value.episode_id) ||
        !Number.isSafeInteger(value.generation) || value.generation < 0 ||
        !validNumber(value.sim_time)) throw new Error("Invalid status");
    runtime.value = value;
    runtime.at = started; // Conservatively include round-trip time in status freshness.
    runtime.failed = false;
  } catch (_) {
    runtime.failed = true;
  } finally {
    runtime.busy = false;
    render();
  }
}

async function pollFrame(feed) {
  if (feed.busy) return;
  feed.busy = true;
  const started = performance.now();
  let nextUrl = null;
  try {
    const response = await get(`/${feed.id}.jpg`, AbortSignal.timeout(1800));
    const frame = {
      epoch: response.headers.get("X-Microduck-Episode"),
      sequence: headerNumber(response, "X-Microduck-Sequence"),
      simTime: headerNumber(response, "X-Microduck-Sim-Time"),
      capture: headerNumber(response, "X-Microduck-Capture-Monotonic"),
      age: headerNumber(response, "X-Preview-Age-S"),
      at: started
    };
    if (!validEpoch(frame.epoch) || !Number.isSafeInteger(frame.sequence)) {
      throw new Error("Invalid provenance");
    }
    const blob = await response.blob();
    const previous = feed.frame;
    if (!previous || previous.epoch !== frame.epoch || previous.sequence !== frame.sequence ||
        previous.capture !== frame.capture) {
      nextUrl = URL.createObjectURL(blob);
      const decoded = new Image();
      decoded.src = nextUrl;
      await decoded.decode(); // A corrupt JPEG never replaces the last valid image.
      const image = feed.node.querySelector("img");
      image.src = nextUrl;
      image.hidden = false;
      feed.node.querySelector(".empty").hidden = true;
      if (feed.url) URL.revokeObjectURL(feed.url);
      feed.url = nextUrl;
      nextUrl = null;
    }
    feed.frame = frame;
    feed.failed = false;
  } catch (_) {
    feed.failed = true;
  } finally {
    if (nextUrl) URL.revokeObjectURL(nextUrl);
    feed.busy = false;
    render();
  }
}

function render() {
  const now = performance.now();
  const status = runtime.value;
  const statusOffline = runtime.failed || !status || now - runtime.at > STATUS_TIMEOUT_MS;
  const statusLabel = document.getElementById("runtime-state");
  statusLabel.dataset.state = statusOffline ? "offline" : status.ready ? "live" : "stale";
  statusLabel.textContent = statusOffline ? "OFFLINE / status unavailable" :
    status.ready ? "READY / source reports" : "NOT READY / source reports";
  if (status) {
    document.getElementById("physics").textContent = status.physics;
    document.getElementById("episode").textContent = status.episode_id;
    document.getElementById("generation").textContent = status.generation;
    document.getElementById("sim-time").textContent = seconds(status.sim_time);
  }
  for (const feed of feeds) {
    const frame = feed.frame;
    const age = frame ? frame.age + (now - frame.at) / 1000 : null;
    let state = "offline";
    let reason = frame ? "Feed unavailable; last image retained." : "Waiting for an actual frame.";
    if (frame && !feed.failed) {
      if (statusOffline) reason = "Status unavailable; image freshness cannot be confirmed.";
      else if (frame.epoch !== status.episode_id) {
        state = "stale";
        reason = "Capture epoch differs from the current episode.";
      } else if (!status.ready) {
        state = "stale";
        reason = "Source reports not ready; last capture shown.";
      } else if (age > STALE_S) {
        state = "stale";
        reason = "Capture is older than 0.5 s; not a fresh observation.";
      } else {
        state = "live";
        reason = "Recent source capture; no task or policy verdict implied.";
      }
    }
    feed.node.dataset.state = state;
    text(feed.node, ".feed-state", state.toUpperCase());
    text(feed.node, ".image-warning", !frame ? "NO FRAME" : state === "live" ?
      "LIVE · RECENT CAPTURE" : `${state.toUpperCase()} · LAST IMAGE`);
    text(feed.node, ".feed-note", reason);
    if (frame) {
      text(feed.node, ".epoch", frame.epoch);
      text(feed.node, ".sequence", String(frame.sequence));
      text(feed.node, ".sim-time", seconds(frame.simTime));
      text(feed.node, ".age", seconds(age));
    }
  }
}

function poll() {
  pollStatus();
  feeds.forEach(pollFrame); // Independent requests, never presented as a synchronized pair.
}
poll();
setInterval(poll, POLL_MS);
setInterval(render, 100); // Age increases even while a request stalls or the feed stops.
