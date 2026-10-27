import hashlib
import json
from urllib.error import URLError

import pytest

from microduck_workshop.assets import AssetError, fetch_assets, load_manifest


def example(tmp_path, *, license="Apache-2.0"):
    data = b"public test artifact"
    value = {
        "schema_version": 1,
        "file_count": 1,
        "files": [
            {
                "path": "robot/test.xml",
                "url": "https://raw.githubusercontent.com/pollen-robotics/microduck_rl/"
                + "a" * 40
                + "/test.xml",
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "license": license,
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    return path, value, data


def test_manifest_accepts_pinned_public_artifact(tmp_path):
    path, _, _ = example(tmp_path)
    assert len(load_manifest(path)["files"]) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "../escape"),
        ("path", "/absolute"),
        ("path", "robot/../../escape"),
        ("path", r"robot\escape"),
        ("url", "https://raw.githubusercontent.com/pollen-robotics/microduck_rl/main/test.xml"),
        ("url", "https://evil.example/a"),
        ("url", "http://huggingface.co/a"),
        ("sha256", "not-a-sha"),
        ("bytes", True),
        ("bytes", -1),
    ],
)
def test_manifest_refuses_unsafe_or_unpinned_entries(tmp_path, field, value):
    path, manifest, _ = example(tmp_path)
    manifest["files"][0][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


def test_manifest_count_and_duplicate_paths_are_hard_constraints(tmp_path):
    path, manifest, _ = example(tmp_path)
    manifest["files"].append(manifest["files"][0])
    manifest["file_count"] = 2
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)
    manifest["files"] = manifest["files"][:1]
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


def test_verified_cache_is_read_without_network(tmp_path):
    path, _, data = example(tmp_path)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    result = fetch_assets(path, dest)
    assert result["verified_files"] == 1 and result["downloaded_files"] == 0


def test_corrupt_cache_is_not_silently_replaced(tmp_path):
    path, _, _ = example(tmp_path)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(b"wrong")
    with pytest.raises(AssetError):
        fetch_assets(path, dest)
    assert (dest / "robot/test.xml").read_bytes() == b"wrong"


def test_mesh_license_requires_explicit_acknowledgment(tmp_path):
    path, _, data = example(tmp_path, license="CC-BY-NC-SA-4.0")
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    with pytest.raises(AssetError):
        fetch_assets(path, dest)
    assert fetch_assets(path, dest, accept_mesh_license=True)["verified_files"] == 1


def test_fresh_download_retries_transient_network_failure_then_checks_hash(tmp_path, monkeypatch):
    import io

    from microduck_workshop import assets

    path, _, data = example(tmp_path)
    attempts = []

    class Opener:
        def open(self, request, timeout):
            attempts.append(request.full_url)
            if len(attempts) == 1:
                raise URLError("temporary DNS failure")
            return io.BytesIO(data)

    monkeypatch.setattr(assets, "build_opener", lambda *args: Opener())
    result = fetch_assets(path, tmp_path / "cache")
    assert len(attempts) == 2
    assert result["downloaded_files"] == 1
    assert (tmp_path / "cache/robot/test.xml").read_bytes() == data


def test_bad_download_never_becomes_an_admitted_file(tmp_path, monkeypatch):
    import io

    from microduck_workshop import assets

    path, _, data = example(tmp_path)

    class Opener:
        def open(self, request, timeout):
            return io.BytesIO(b"x" * len(data))

    monkeypatch.setattr(assets, "build_opener", lambda *args: Opener())
    with pytest.raises(AssetError, match="Hash mismatch"):
        fetch_assets(path, tmp_path / "cache")
    assert not (tmp_path / "cache/robot/test.xml").exists()


def test_symlink_parent_cannot_escape_cache(tmp_path):
    path, _, data = example(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "test.xml").write_bytes(data)
    dest = tmp_path / "cache"
    dest.mkdir()
    (dest / "robot").symlink_to(outside, target_is_directory=True)
    with pytest.raises(AssetError):
        fetch_assets(path, dest)
