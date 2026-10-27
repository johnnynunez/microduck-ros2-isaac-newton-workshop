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


@pytest.mark.parametrize("name", ["download-receipt.json", "download-receipt.json/child"])
def test_manifest_reserves_receipt_namespace_before_writes(tmp_path, monkeypatch, name):
    from microduck_workshop import assets

    def no_fetch(*args):
        pytest.fail("Conflicting manifest reached the download stage")

    monkeypatch.setattr(assets, "_fetch_one", no_fetch)
    path, manifest, _ = example(tmp_path)
    manifest["files"][0]["path"] = name
    path.write_text(json.dumps(manifest))
    dest = tmp_path / "cache"
    with pytest.raises(AssetError, match="reserved"):
        fetch_assets(path, dest)
    assert not dest.exists()


@pytest.mark.parametrize(
    "suffix",
    [
        "../main/test.xml",
        "../../../../another-owner/another-repo/main/test.xml",
        "./test.xml",
        "%2e%2e/main/test.xml",
        ".%2E/main/test.xml",
        "%2E/test.xml",
        "folder/%2e%2e/test.xml",
        "folder%2ftest.xml",
        "folder%2F..%2ftest.xml",
        "folder%5ctest.xml",
        r"folder\test.xml",
        "folder//test.xml",
        "folder/%252e%252e/test.xml",
        "folder%252ftest.xml",
        "bad%zz.xml",
        "bad%.xml",
        "bad\nname.xml",
        "bad\tname.xml",
    ],
)
def test_manifest_rejects_noncanonical_url_paths_without_repair(tmp_path, suffix):
    path, manifest, _ = example(tmp_path)
    manifest["files"][0]["url"] = manifest["files"][0]["url"].rsplit("/", 1)[0] + "/" + suffix
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


@pytest.mark.parametrize(
    "authority",
    [
        "raw.githubusercontent.com:invalid",
        "raw.githubusercontent.com:0",
        "raw.githubusercontent.com:",
        "raw.githubusercontent.com:443",
    ],
)
def test_manifest_rejects_explicit_or_invalid_ports_as_asset_errors(tmp_path, authority):
    path, manifest, _ = example(tmp_path)
    manifest["files"][0]["url"] = manifest["files"][0]["url"].replace(
        "raw.githubusercontent.com", authority
    )
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


def test_huggingface_encoded_separator_cannot_be_an_artifact_name(tmp_path):
    path, manifest, _ = example(tmp_path)
    manifest["files"][0]["url"] = (
        "https://huggingface.co/pollen-robotics/microduck-policies/resolve/"
        + "a" * 40
        + "/..%2fmain%2fmodel.onnx"
    )
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


def test_https_huggingface_cdn_redirects_remain_supported():
    import io
    from http.client import HTTPMessage
    from urllib.request import Request

    from microduck_workshop.assets import _HttpsRedirect

    request = Request(
        "https://huggingface.co/pollen-robotics/microduck-policies/resolve/"
        + "a" * 40
        + "/model.onnx"
    )
    cdn_url = "https://cas-bridge.xethub.hf.co/xet-bridge-us/fixture?Signature=fixture"
    response, headers = io.BytesIO(), HTTPMessage()
    redirected = _HttpsRedirect().redirect_request(
        request, response, 302, "Found", headers, cdn_url
    )
    assert redirected is not None and redirected.full_url == cdn_url
    with pytest.raises(AssetError):
        _HttpsRedirect().redirect_request(request, response, 302, "Found", headers, "http://cdn/x")


@pytest.mark.parametrize(
    "field,value",
    [
        ("url", "bad\ud800.xml"),
        ("url", "bad-low\udfff.xml"),
        ("url", "bad%ED%A0%80.xml"),
        ("path", "robot/bad\ud800.xml"),
        ("path", "robot/bad\x00.xml"),
    ],
)
def test_manifest_rejects_unencodable_or_nul_names(tmp_path, field, value):
    path, manifest, _ = example(tmp_path)
    if field == "url":
        value = manifest["files"][0]["url"].rsplit("/", 1)[0] + "/" + value
    manifest["files"][0][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


@pytest.mark.parametrize(
    "failure_stage", ["url_encoding", "fdopen", "request", "opener", "response"]
)
def test_download_setup_failures_close_temporary_descriptors(tmp_path, monkeypatch, failure_stage):
    import errno
    import os

    from microduck_workshop import assets

    _, manifest, _ = example(tmp_path)
    entry = manifest["files"][0]
    descriptors = []
    mkstemp = assets.tempfile.mkstemp

    def track_temporary(*args, **kwargs):
        fd, name = mkstemp(*args, **kwargs)
        descriptors.append((fd, name))
        return fd, name

    def fail(*args, **kwargs):
        raise ValueError("injected setup failure")

    monkeypatch.setattr(assets.tempfile, "mkstemp", track_temporary)
    if failure_stage == "url_encoding":
        entry["url"] += "\ud800"
    elif failure_stage == "fdopen":
        monkeypatch.setattr(assets.os, "fdopen", fail)
    elif failure_stage == "request":
        monkeypatch.setattr(assets, "Request", fail)
    elif failure_stage == "opener":
        monkeypatch.setattr(assets, "build_opener", fail)
    else:
        from types import SimpleNamespace

        monkeypatch.setattr(assets, "build_opener", lambda *args: SimpleNamespace(open=fail))
    try:
        for _ in range(3):
            with pytest.raises(AssetError):
                assets._fetch_once(tmp_path / "cache", entry)
        for fd, name in descriptors:
            with pytest.raises(OSError) as closed:
                os.fstat(fd)
            assert closed.value.errno == errno.EBADF
            assert not assets.Path(name).exists()
    finally:
        # Clean the original bug's leaked fixture descriptors even on RED.
        for fd, _ in descriptors:
            try:
                os.close(fd)
            except OSError:
                pass


@pytest.mark.parametrize("value", [[], None, 1, True, "manifest"])
def test_manifest_nonobject_top_level_raises_asset_error(tmp_path, value):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value))
    with pytest.raises(AssetError):
        load_manifest(path)


@pytest.mark.parametrize("schema_version", [True, False, 1.0, "1", None])
def test_manifest_schema_version_must_be_an_exact_integer(tmp_path, schema_version):
    path, manifest, _ = example(tmp_path)
    manifest["schema_version"] = schema_version
    path.write_text(json.dumps(manifest))
    with pytest.raises(AssetError):
        load_manifest(path)


@pytest.mark.parametrize("license_value", [[], {}, True, None])
def test_manifest_malformed_license_raises_asset_error(tmp_path, license_value):
    path, manifest, _ = example(tmp_path)
    manifest["files"][0]["license"] = license_value
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


def test_receipt_hashes_exact_validated_manifest_snapshot(tmp_path, monkeypatch):
    from microduck_workshop import assets

    path, manifest, data = example(tmp_path)
    # Noncanonical whitespace proves the receipt hashes bytes, not reserialized JSON.
    admitted_bytes = (json.dumps(manifest, indent=3) + "\n\n").encode()
    path.write_bytes(admitted_bytes)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    original_fetch = assets._fetch_one

    def verify_then_edit(root, entry):
        downloaded = original_fetch(root, entry)
        manifest["files"][0]["sha256"] = "f" * 64
        path.write_text(json.dumps(manifest))
        return downloaded

    monkeypatch.setattr(assets, "_fetch_one", verify_then_edit)
    result = fetch_assets(path, dest)
    assert result["manifest_sha256"] == hashlib.sha256(admitted_bytes).hexdigest()
    assert result["manifest_sha256"] != hashlib.sha256(path.read_bytes()).hexdigest()
    assert json.loads((dest / "download-receipt.json").read_text()) == result


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


@pytest.mark.parametrize("link_kind", ["symlink", "hardlink"])
def test_receipt_links_cannot_clobber_outside_files(tmp_path, link_kind):
    import os

    path, _, data = example(tmp_path)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"do not overwrite")
    receipt = dest / "download-receipt.json"
    if link_kind == "symlink":
        receipt.symlink_to(outside)
    else:
        os.link(outside, receipt)
    try:
        with pytest.raises(AssetError, match="receipt|symlink"):
            fetch_assets(path, dest)
    finally:
        assert outside.read_bytes() == b"do not overwrite"


def test_receipt_is_atomically_replaced_not_truncated(tmp_path, monkeypatch):
    from microduck_workshop import assets

    path, _, data = example(tmp_path)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    receipt = dest / "download-receipt.json"
    receipt.write_bytes(b"previous receipt")
    original_replace = assets.os.replace
    replacements = []

    def replace(source, target, **kwargs):
        assert receipt.read_bytes() == b"previous receipt"
        replacements.append(target)
        return original_replace(source, target, **kwargs)

    monkeypatch.setattr(assets.os, "replace", replace)
    with receipt.open("rb") as previous_inode:
        result = fetch_assets(path, dest)
        assert previous_inode.read() == b"previous receipt"
    assert replacements
    assert json.loads(receipt.read_text()) == result


def test_canonical_public_manifest_still_admits_all_files():
    from microduck_workshop.assets import default_manifest

    manifest = load_manifest(default_manifest())
    assert manifest["file_count"] == len(manifest["files"]) == 121
    assert len({entry["path"] for entry in manifest["files"]}) == 121
    assert sum(entry["bytes"] for entry in manifest["files"]) == 24_774_857


def test_receipt_publish_failure_preserves_previous_receipt(tmp_path, monkeypatch):
    from microduck_workshop import assets

    path, _, data = example(tmp_path)
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    receipt = dest / "download-receipt.json"
    receipt.write_bytes(b"previous receipt")

    def fail_replace(*args, **kwargs):
        raise OSError("injected publish failure")

    monkeypatch.setattr(assets.os, "replace", fail_replace)
    with pytest.raises(AssetError, match="receipt"):
        fetch_assets(path, dest)
    assert receipt.read_bytes() == b"previous receipt"
    assert not list(dest.glob(".receipt-*"))


def test_receipt_cleanup_failure_still_closes_descriptors(tmp_path, monkeypatch):
    import os

    from microduck_workshop import assets

    descriptors = []
    original_open = os.open

    def track_open(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        descriptors.append(fd)
        return fd

    def fail_unlink(*args, **kwargs):
        raise PermissionError("injected cleanup failure")

    monkeypatch.setattr(assets.os, "open", track_open)
    monkeypatch.setattr(assets.os, "unlink", fail_unlink)
    try:
        with pytest.raises(PermissionError):
            assets._write_receipt(tmp_path, {"fixture": "cleanup"})
        for fd in descriptors:
            with pytest.raises(OSError):
                os.fstat(fd)
    finally:
        for fd in descriptors:
            try:
                os.close(fd)
            except OSError:
                pass


def test_receipt_directory_descriptor_prevents_redirected_publication(tmp_path, monkeypatch):
    from microduck_workshop import assets

    dest, moved, outside = tmp_path / "cache", tmp_path / "moved", tmp_path / "outside"
    dest.mkdir()
    outside.mkdir()
    outside_receipt = outside / "download-receipt.json"
    outside_receipt.write_bytes(b"do not overwrite")
    original_replace = assets.os.replace

    def swap_directory_then_replace(source, target, **kwargs):
        dest.rename(moved)
        dest.symlink_to(outside, target_is_directory=True)
        return original_replace(source, target, **kwargs)

    monkeypatch.setattr(assets.os, "replace", swap_directory_then_replace)
    assets._write_receipt(dest, {"fixture": "metadata only"})
    assert outside_receipt.read_bytes() == b"do not overwrite"
    assert json.loads((moved / "download-receipt.json").read_text()) == {"fixture": "metadata only"}
    assert not list(moved.glob(".receipt-*"))


@pytest.mark.parametrize("malformation", ["top_level", "schema_boolean", "port", "unicode"])
def test_asset_cli_normalizes_admission_failures(tmp_path, monkeypatch, capsys, malformation):
    from microduck_workshop import assets

    path, manifest, data = example(tmp_path)
    if malformation == "top_level":
        manifest = []
    elif malformation == "schema_boolean":
        manifest["schema_version"] = True
    elif malformation == "port":
        manifest["files"][0]["url"] = manifest["files"][0]["url"].replace(
            "raw.githubusercontent.com", "raw.githubusercontent.com:invalid"
        )
    else:
        manifest["files"][0]["url"] += "\ud800"
    path.write_text(json.dumps(manifest))
    dest = tmp_path / "cache"
    (dest / "robot").mkdir(parents=True)
    (dest / "robot/test.xml").write_bytes(data)
    monkeypatch.setattr(
        "sys.argv", ["assets", "fetch", "--manifest", str(path), "--destination", str(dest)]
    )
    with pytest.raises(SystemExit) as failure:
        assets.main()
    assert failure.value.code == 2
    output = capsys.readouterr()
    assert "Asset admission refused:" in output.err
    assert "Traceback" not in output.err and not output.out


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
