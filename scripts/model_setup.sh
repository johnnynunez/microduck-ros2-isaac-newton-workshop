#!/usr/bin/env bash
# Build only the pinned upstream source; never install globally.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 - "$ROOT" "$@" <<'PY'
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

root = Path(sys.argv[1])
parser = argparse.ArgumentParser(description="Pinned CUDA llama.cpp and Qwen3.8 GGUF bootstrap")
group = parser.add_mutually_exclusive_group()
group.add_argument('--plan', action='store_true', help='print immutable inputs without downloading')
group.add_argument('--build-only', action='store_true', help='build source, skip weights')
group.add_argument('--download-only', action='store_true', help='verify/download weights, skip build')
group.add_argument('--verify-only', action='store_true', help='offline hashes and build receipt check')
args = parser.parse_args(sys.argv[2:])
manifest = json.loads((root / 'provenance/local_model.json').read_text())
plan = {k: manifest[k] for k in ('llama_cpp', 'model', 'cuda_architectures')}
jobs = os.environ.get('MODEL_BUILD_JOBS', '8')
if not jobs.isdecimal() or not 1 <= int(jobs) <= 8:
    parser.error('MODEL_BUILD_JOBS must be 1..8')
plan['build_jobs'] = int(jobs)
if args.plan:
    print(json.dumps(plan, indent=2))
    sys.exit(0)
cache = Path(os.environ.get('MODEL_CACHE', root / '.workshop/model-cache')).resolve()
cache.mkdir(parents=True, exist_ok=True)
lock = (cache / 'setup.lock').open('a')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    parser.error('another setup owns this cache')
if not args.verify_only:
    (cache / 'run').mkdir(exist_ok=True)
    server_lock = (cache / 'run/server.lock').open('a')
    try:
        fcntl.flock(server_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error('stop the model before setup; its artifacts must not change while serving')


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def verify(path, sha):
    if not path.is_file():
        parser.error(f'missing artifact: {path.name}; run setup first')
    if digest(path) != sha:
        parser.error(f'SHA256 mismatch: {path.name}; preserved for inspection, not used')


def fetch(url, path, sha):
    if path.exists():
        verify(path, sha)
        return
    partial = path.with_name(path.name + '.partial')
    # No token is required; no implicit Hugging Face client/configuration is used.
    subprocess.run(['curl', '--disable', '--fail', '--location', '--http1.1', '--proto', '=https',
                    '--proto-redir', '=https', '--retry-all-errors', '--retry', '3',
                    '--connect-timeout', '20',
                    '--max-time', '3600', '--continue-at', '-', '--output', str(partial), url],
                   check=True)
    verify(partial, sha)
    partial.replace(path)


source = manifest['llama_cpp']
model = manifest['model']
archive = cache / 'source.tar.gz'
weights = cache / model['filename']
source_dir = cache / ('llama.cpp-' + source['revision'])
build = cache / ('build-' + source['revision'])
receipt = cache / 'build.json'
if args.verify_only:
    verify(archive, source['sha256'])
    verify(weights, model['sha256'])
    data = json.loads(receipt.read_text())
    if data['revision'] != source['revision'] or data['cuda_architectures'] != ['89', '120']:
        parser.error('build receipt does not match pinned CUDA build')
    for relative, sha in data['artifacts'].items():
        verify(build / relative, sha)
    print('Verified pinned source, GGUF and compiled artifacts (offline).')
    sys.exit(0)
if not args.download_only:
    fetch(source['archive_url'], archive, source['sha256'])
    for command in ('cmake', 'ninja', 'c++'):
        if shutil.which(command) is None:
            parser.error(f'missing prerequisite: {command}; see docs/local_model.md')
    cuda = os.environ.get('CUDACXX') or shutil.which('nvcc')
    if not cuda and Path('/usr/local/cuda/bin/nvcc').is_file():
        cuda = '/usr/local/cuda/bin/nvcc'
    if not cuda:
        parser.error('CUDA Toolkit >=12.8 required (set CUDACXX); no global install is attempted')
    # Re-extract verified upstream source every build: never build edited cached sources.
    if source_dir.exists():
        shutil.rmtree(source_dir)
    with tarfile.open(archive) as tar:
        tar.extractall(cache, filter='data')
    # A previous build may have fetched mutable UI assets despite BUILD_UI=OFF.
    # Remove only this owned build's UI cache, so OFF cannot embed stale downloads.
    ui_dist = build / 'tools/ui/dist'
    if ui_dist.exists():
        shutil.rmtree(ui_dist)
    subprocess.run(['cmake', '-S', str(source_dir), '-B', str(build), '-G', 'Ninja',
                    '-DCMAKE_BUILD_TYPE=Release', '-DGGML_CUDA=ON',
                    '-DCMAKE_CUDA_ARCHITECTURES=89;120', '-DCMAKE_CUDA_COMPILER=' + cuda,
                    '-DGGML_NATIVE=OFF', '-DLLAMA_BUILD_TESTS=OFF',
                    '-DLLAMA_BUILD_NUMBER=0', '-DLLAMA_BUILD_COMMIT=' + source['revision'],
                    '-DGGML_BUILD_NUMBER=0', '-DGGML_BUILD_COMMIT:STRING=' + source['revision'],
                    '-DLLAMA_BUILD_EXAMPLES=OFF', '-DLLAMA_BUILD_APP=OFF',
                    '-DLLAMA_BUILD_UI=OFF', '-DLLAMA_USE_PREBUILT_UI=OFF',
                    '-DLLAMA_OPENSSL=OFF'], check=True,
                   env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(cache)})
    subprocess.run(['cmake', '--build', str(build), '--target', 'llama-server',
                    '-j', jobs], check=True,
                   env={**os.environ, 'GIT_CEILING_DIRECTORIES': str(cache)})
    subprocess.run([str(build / 'bin/llama-server'), '--version'], check=True)
    artifacts = {str(p.relative_to(build)): digest(p) for p in sorted((build / 'bin').iterdir())
                 if p.is_file() and not p.is_symlink()}
    receipt.write_text(json.dumps(dict(revision=source['revision'],
        cuda_architectures=manifest['cuda_architectures'], artifacts=artifacts,
        cmake_cache_sha256=digest(build / 'CMakeCache.txt')), indent=2) + '\n')
if not args.build_only:
    fetch(model['url'], weights, model['sha256'])
print('Setup completed; no server was started. See scripts/model_start.sh.')
PY
