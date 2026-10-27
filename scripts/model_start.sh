#!/usr/bin/env bash
# Foreground supervisor: use a bounded service manager for unattended operation.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1])
parser = argparse.ArgumentParser(description='Serve pinned Qwen3.8 locally, one GPU/sequence')
parser.add_argument('--plan', action='store_true', help='show launch configuration without starting')
args = parser.parse_args(sys.argv[2:])
manifest = json.loads((root / 'provenance/local_model.json').read_text())
cache = Path(os.environ.get('MODEL_CACHE', root / '.workshop/model-cache')).resolve()
binary = cache / ('build-' + manifest['llama_cpp']['revision']) / 'bin/llama-server'
gpu = os.environ.get('MODEL_GPU', os.environ.get('CUDA_VISIBLE_DEVICES', '0'))
port = os.environ.get('MODEL_PORT', '18511')
context = os.environ.get('MODEL_CONTEXT', '4096')
import re
if not re.fullmatch(r'(?:[0-9]+|GPU-[0-9a-fA-F-]{36})', gpu):
    parser.error('MODEL_GPU must select one physical GPU index or UUID')
if not port.isdecimal() or not 1024 <= int(port) <= 65535:
    parser.error('MODEL_PORT must be 1024..65535')
if not context.isdecimal() or not 1024 <= int(context) <= 4096:
    parser.error('MODEL_CONTEXT must be 1024..4096; one sequence only')
command = [str(binary), '--model', str(cache / manifest['model']['filename']),
           '--alias', manifest['model']['served_name'], '--host', '127.0.0.1', '--port', port,
           '--ctx-size', context, '--parallel', '1', '--n-gpu-layers', 'all',
           '--batch-size', '256', '--ubatch-size', '128', '--threads', '8',
           '--threads-batch', '8', '--n-predict', '1024', '--cache-type-k', 'f16',
           '--cache-type-v', 'f16', '--flash-attn', 'on', '--fit', 'off',
           '--jinja', '--chat-template-kwargs', '{"enable_thinking":false}',
           '--no-context-shift', '--no-webui']
plan = dict(command=command, gpu=gpu, min_free_vram_mib=24576)
if args.plan:
    print(json.dumps(plan, indent=2))
    sys.exit(0)
import socket
with socket.socket() as sock:
    try:
        sock.bind(('127.0.0.1', int(port)))
    except OSError:
        parser.error('port is already in use; no existing process will be stopped')
if not binary.is_file() or not (cache / 'build.json').is_file():
    parser.error('run model_setup.sh first; pinned build receipt/binary missing')
import fcntl
import signal
import subprocess
import time
import urllib.request

run = cache / 'run'
run.mkdir(parents=True, exist_ok=True)
lock = (run / 'server.lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    parser.error('this cache already has a supervised server')
# Check bytes on every launch, not just the first download. No network in this step.
subprocess.run(['bash', str(root / 'scripts/model_setup.sh'), '--verify-only'], check=True,
               env={**os.environ, 'MODEL_CACHE': str(cache)})
free = subprocess.check_output(['nvidia-smi', '-i', gpu, '--query-gpu=memory.free',
                               '--format=csv,noheader,nounits'], text=True, timeout=10).strip()
if not free.isdecimal() or int(free) < plan['min_free_vram_mib']:
    parser.error('at least 24576 MiB free VRAM is required; stop training first')
# Drop inherited llama-server option environment overrides (including API keys/host).
env = {k: v for k, v in os.environ.items() if not k.startswith('LLAMA_')}
env['CUDA_VISIBLE_DEVICES'] = gpu
env['OMP_NUM_THREADS'] = '8'
state = run / 'server.json'
log = (run / 'server.log').open('a', buffering=1)
log.write('\nSTART ' + json.dumps(plan) + '\n')
process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
record = dict(pid=process.pid, executable=str(binary.resolve()), port=int(port), gpu=gpu,
              start_ticks=Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19])
state.write_text(json.dumps(record, indent=2) + '\n')
stop_requested = False


def request_stop(signum, frame):
    global stop_requested
    stop_requested = True
    if process.poll() is None:
        process.terminate()


signal.signal(signal.SIGTERM, request_stop)
signal.signal(signal.SIGINT, request_stop)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
try:
    deadline = time.monotonic() + 240
    ready = False
    while time.monotonic() < deadline and process.poll() is None and not stop_requested:
        try:
            with opener.open(f'http://127.0.0.1:{port}/health', timeout=2) as response:
                ready = json.load(response).get('status') == 'ok'
            if ready:
                break
        except (OSError, ValueError):
            pass
        time.sleep(1)
    if not ready:
        raise SystemExit('Model did not become healthy; inspect ' + str(run / 'server.log'))
    print(f'READY http://127.0.0.1:{port}/v1 model=qwen3.8-27b pid={process.pid}', flush=True)
    code = process.wait()
    if code not in (0, -signal.SIGTERM) and not stop_requested:
        raise SystemExit(code)
finally:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    # A different supervisor can never own this state while our lock is held.
    state.unlink(missing_ok=True)
    log.close()
PY
