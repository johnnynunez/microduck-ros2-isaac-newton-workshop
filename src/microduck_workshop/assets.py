"""Download separately licensed public assets with immutable identities and exact hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class AssetError(ValueError):
    """Asset admission failed; no unverified replacement is used."""


class _HttpsRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != "https":
            raise AssetError("Refusing a non-HTTPS download redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(Path(path).read_text())
    except (OSError, ValueError) as exc:
        raise AssetError(f"Cannot read asset manifest: {exc}") from exc
    entries = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(entries, list) or not entries:
        raise AssetError("Expected nonempty schema-version-1 manifest")
    if type(manifest.get("file_count")) is not int or manifest["file_count"] != len(entries):
        raise AssetError("Manifest file_count does not match its entries")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "path",
            "url",
            "sha256",
            "bytes",
            "license",
        }:
            raise AssetError("Each entry requires exactly path/url/sha256/bytes/license")
        name = entry["path"]
        if not isinstance(name, str) or not name or "\\" in name or ":" in name:
            raise AssetError("Invalid relative asset path")
        components = name.split("/")
        if PurePosixPath(name).is_absolute() or any(p in ("", ".", "..") for p in components):
            raise AssetError("Asset path traversal or normalization is forbidden")
        if name in seen:
            raise AssetError("Duplicate asset destination")
        seen.add(name)
        if not isinstance(entry["sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", entry["sha256"]
        ):
            raise AssetError("Invalid literal SHA-256")
        if type(entry["bytes"]) is not int or not 0 < entry["bytes"] <= 100_000_000:
            raise AssetError("Invalid declared file size")
        if entry["license"] not in {"Apache-2.0", "CC-BY-NC-SA-4.0"}:
            raise AssetError("Unknown asset license")
        if not isinstance(entry["url"], str):
            raise AssetError("URL must be a string")
        parsed = urlsplit(entry["url"])
        if (
            parsed.scheme != "https"
            or parsed.username
            or parsed.password
            or parsed.port
            or parsed.query
            or parsed.fragment
        ):
            raise AssetError("Expected a credential-free immutable HTTPS source URL")
        if parsed.hostname == "raw.githubusercontent.com":
            valid = re.fullmatch(
                r"/pollen-robotics/(microduck|microduck_rl)/[0-9a-f]{40}/.+", parsed.path
            )
        elif parsed.hostname == "huggingface.co":
            valid = re.fullmatch(
                r"/pollen-robotics/microduck-policies/resolve/[0-9a-f]{40}/[^/]+", parsed.path
            )
        else:
            valid = False
        if not valid:
            raise AssetError(
                "Only allowlisted public Pollen sources pinned by full commit are admitted"
            )
    return manifest


def _destination(root: Path, name: str) -> Path:
    target = root.joinpath(*PurePosixPath(name).parts)
    for part in [target, *target.parents]:
        if part == root.parent:
            break
        if part.is_symlink():
            raise AssetError(f"Refusing symlink in asset path: {name}")
    if not target.resolve().is_relative_to(root.resolve()):
        raise AssetError("Asset escaped its destination root")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _check(path: Path, entry: dict) -> None:
    if not path.is_file() or path.stat().st_size != entry["bytes"]:
        raise AssetError(
            f"Size mismatch for {entry['path']}; existing files are not silently replaced"
        )
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != entry["sha256"]:
        raise AssetError(
            f"Hash mismatch for {entry['path']}; expected {entry['sha256']}, got {digest}"
        )


def _fetch_once(root: Path, entry: dict) -> bool:
    target = _destination(root, entry["path"])
    if target.exists():
        _check(target, entry)
        return False
    fd, temporary = tempfile.mkstemp(prefix=".download-", dir=target.parent)
    temporary = Path(temporary)
    try:
        request = Request(
            quote(entry["url"], safe=":/%"), headers={"User-Agent": "microduck-workshop/0.1"}
        )
        opener = build_opener(_HttpsRedirect())
        with os.fdopen(fd, "wb") as output, opener.open(request, timeout=45) as response:
            count = 0
            while block := response.read(1 << 16):
                count += len(block)
                if count > entry["bytes"]:
                    raise AssetError(f"Download exceeds declared size: {entry['path']}")
                output.write(block)
        _check(temporary, entry)
        if target.exists():
            _check(target, entry)
        else:
            os.replace(temporary, target)
        return True
    except AssetError:
        raise
    except Exception as exc:
        raise AssetError(
            f"Download failed for {entry['path']}: {type(exc).__name__}: {exc}"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _fetch_one(root: Path, entry: dict) -> bool:
    # GET retries are bounded and only cover transport failures, never a hash mismatch.
    for attempt in range(3):
        try:
            return _fetch_once(root, entry)
        except AssetError as exc:
            if attempt == 2 or not isinstance(exc.__cause__, (URLError, TimeoutError)):
                raise
            time.sleep(0.25 * (2**attempt))
    raise AssertionError("Unreachable retry state")


def fetch_assets(
    manifest_path: Path, destination: Path, *, accept_mesh_license: bool = False
) -> dict:
    manifest = load_manifest(manifest_path)
    if (
        any(e["license"] == "CC-BY-NC-SA-4.0" for e in manifest["files"])
        and not accept_mesh_license
    ):
        raise AssetError(
            "Pollen meshes are CC BY-NC-SA 4.0. Review your permissions and acknowledge with --accept-mesh-license."
        )
    root = Path(destination).absolute()
    if root.is_symlink():
        raise AssetError("Asset root cannot be a symlink")
    root.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        downloaded = list(pool.map(lambda e: _fetch_one(root, e), manifest["files"]))
    result = {
        "status": "PASS",
        "verified_files": len(manifest["files"]),
        "downloaded_files": sum(downloaded),
        "bytes": sum(e["bytes"] for e in manifest["files"]),
        "manifest_sha256": hashlib.sha256(Path(manifest_path).read_bytes()).hexdigest(),
        "scope": "Public source identity and bytes only; not physics or policy behavior validation",
    }
    receipt = root / "download-receipt.json"
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    return result


def default_manifest() -> Path:
    packaged = Path(__file__).parent / "provenance" / "sources.json"
    if packaged.is_file():
        return packaged
    return Path(__file__).resolve().parents[2] / "provenance" / "sources.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["fetch"])
    parser.add_argument("--manifest", type=Path, default=default_manifest())
    parser.add_argument("--destination", type=Path, default=Path(".cache/assets"))
    parser.add_argument("--accept-mesh-license", action="store_true")
    args = parser.parse_args()
    try:
        result = fetch_assets(
            args.manifest, args.destination, accept_mesh_license=args.accept_mesh_license
        )
    except AssetError as exc:
        parser.exit(2, f"Asset admission refused: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
