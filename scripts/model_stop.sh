#!/usr/bin/env bash
# Stop only the exact locally recorded llama-server, never by port/name matching.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
import json
import os
from pathlib import Path
import select
import signal
import sys

root = Path(sys.argv[1])
parser = argparse.ArgumentParser(description='Stop only this cache\'s verified model process')
parser.parse_args(sys.argv[2:])
cache = Path(os.environ.get('MODEL_CACHE', root / '.workshop/model-cache')).resolve()
state = cache / 'run/server.json'
if not state.exists():
    print('Model is not running (no owned process record).')
    sys.exit(0)
record = json.loads(state.read_text())
pid = record['pid']
if type(pid) is not int or pid <= 1:
    parser.error('identity mismatch; refusing to signal')
manifest = json.loads((root / 'provenance/local_model.json').read_text())
expected = cache / ('build-' + manifest['llama_cpp']['revision']) / 'bin/llama-server'
try:
    # pidfd binds the signal to this process even if its numeric PID is reused.
    fd = os.pidfd_open(pid)
except ProcessLookupError:
    print('Model is not running (recorded process has exited).')
    sys.exit(0)
try:
    proc = Path(f'/proc/{pid}')
    ticks = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
    executable = (proc / 'exe').resolve()
    if ticks != record['start_ticks'] or executable != expected.resolve():
        parser.error('identity mismatch; refusing to signal an unrelated process')
    signal.pidfd_send_signal(fd, signal.SIGTERM)
    poll = select.poll()
    poll.register(fd, select.POLLIN)
    if not poll.poll(30000):
        parser.error('owned process did not stop within 30 seconds; inspect its supervisor')
    print(f'Stopped owned model pid={pid}; exit verified by pidfd.')
finally:
    os.close(fd)
PY
