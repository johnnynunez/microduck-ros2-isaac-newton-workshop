"""Build-time patch safety; no silent mutation of an unreviewed ROS release."""
import ast
import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / 'docker/patch_rclpy_executor.py'
spec = importlib.util.spec_from_file_location('executor_patch', SCRIPT)
assert spec is not None and spec.loader is not None
patch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patch)


@pytest.mark.parametrize('version', ['10.0.9', '10.0.11', patch.VERSION])
def test_unreviewed_source_is_rejected_without_write(version):
    with pytest.raises(RuntimeError, match='Unreviewed rclpy'):
        patch.patched_source(b'not the reviewed executor', version)


def test_build_explicitly_installs_patch_and_keeps_it_in_context():
    docker = SCRIPT.parent
    assert 'COPY docker/patch_rclpy_executor.py' in (docker / 'Dockerfile').read_text()
    assert 'python3 /opt/workshop/patch_rclpy_executor.py' in (docker / 'Dockerfile').read_text()
    assert '!docker/patch_rclpy_executor.py' in (docker / 'Dockerfile.dockerignore').read_text()


@pytest.mark.ros
def test_pinned_real_source_patch_changes_only_no_work_cooperation():
    module = pytest.importorskip('rclpy.executors')
    source = Path(module.__file__).read_bytes()
    # Accept either actual pinned stock or actual candidate, never invent source.
    if patch.REPLACEMENT.encode() in source:
        source = source.replace(patch.REPLACEMENT.encode(), patch.ANCHOR.encode())
    assert hashlib.sha256(source).hexdigest() == patch.SOURCE_SHA256
    result = patch.patched_source(source, patch.VERSION)
    assert result.replace(patch.REPLACEMENT.encode(), patch.ANCHOR.encode()) == source
    before, after = ast.parse(source), ast.parse(result)
    wait_before = next(n for n in ast.walk(before) if isinstance(n, ast.FunctionDef)
                       and n.name == '_wait_for_ready_callbacks')
    wait_after = next(n for n in ast.walk(after) if isinstance(n, ast.FunctionDef)
                      and n.name == '_wait_for_ready_callbacks')
    loop = next(n for n in ast.walk(wait_after) if isinstance(n, ast.While))
    cooperation = loop.body.pop()
    assert ast.unparse(cooperation) == 'if not yielded_work:\n    time.sleep(0)'
    assert ast.dump(wait_before) == ast.dump(wait_after)
    with pytest.raises(RuntimeError, match='Unreviewed rclpy'):
        patch.patched_source(result, patch.VERSION)  # double-patch fails closed
