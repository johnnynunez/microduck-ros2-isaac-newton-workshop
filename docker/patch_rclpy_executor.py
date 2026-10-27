"""Explicit build-time rclpy 10.0.10 executor fairness patch.

Never applied implicitly at import/startup. Docker builds fail closed on source
or version drift. The wheel/apt payload is intentionally changed, with original,
patched and installer hashes emitted as a retained image receipt.
"""
import hashlib
import importlib.metadata
import json
from pathlib import Path

VERSION = '10.0.10'
SOURCE_SHA256 = '0830da415e9a63732b8a8bba734883110d04a4be7b21adcf232ac0567332a4a7'
ANCHOR = '                raise TimeoutException()\n        if self._is_shutdown:\n'
REPLACEMENT = '''                raise TimeoutException()

            # A wakeup need not produce a dispatchable handler (including events).
            # A zero-duration OS wait lets GIL contenders actually run. sched_yield
            # alone fails under SCHED_OTHER; no fixed delay/backoff is introduced.
            if not yielded_work:
                time.sleep(0)
        if self._is_shutdown:
'''


def patched_source(source: bytes, version: str) -> bytes:
    if version != VERSION or hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise RuntimeError('Unreviewed rclpy version/source; rebase and revalidate fairness patch')
    text = source.decode('utf-8')
    if text.count(ANCHOR) != 1:
        raise RuntimeError('Executor no-work boundary is not unique')
    result = text.replace(ANCHOR, REPLACEMENT).encode('utf-8')
    compile(result, 'rclpy/executors.py', 'exec')
    return result


def main():
    import rclpy.executors
    path = Path(rclpy.executors.__file__)
    version = importlib.metadata.version('rclpy')
    result = patched_source(path.read_bytes(), version)
    path.write_bytes(result)
    receipt = {'rclpy_version': version, 'path': str(path),
               'original_sha256': SOURCE_SHA256,
               'patched_sha256': hashlib.sha256(result).hexdigest(),
               'installer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               'change': 'zero-duration OS wait only after a complete no-handler iteration'}
    path.with_name('executor-fairness-receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
