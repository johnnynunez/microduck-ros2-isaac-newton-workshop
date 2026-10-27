"""Publication integrity only: this manifest never authorizes a runtime policy."""

import hashlib
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "provenance/public_redaction_manifest.json"
REQUIRED = {
    "provenance/native_policy_default_revalidation.json",
    "provenance/student_policy/attempt01_training_receipt.json",
    "provenance/student_policy/native_handoff.json",
    "provenance/student_policy/training_receipt.json",
}


def test_public_redactions_are_explicit_and_match_published_bytes():
    assert MANIFEST.is_file(), "public copies need an explicit dual-hash redaction manifest"
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["schema_version"] == 1
    assert manifest["kind"] == "public_sanitized_historical_evidence"
    assert manifest["deployable"] is False
    assert manifest["runtime_authorization"] is False
    assert manifest["transformation"]["kind"] == "literal_checkout_prefix_substitution"
    assert manifest["transformation"]["replacement"] == "${WORKSHOP_ROOT}"
    entries = manifest["files"]
    paths = [entry["path"] for entry in entries]
    assert REQUIRED <= set(paths)
    assert len(paths) == len(set(paths))
    for entry in entries:
        path = Path(entry["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert path.parts[0] == "provenance"
        for key in ("original_sha256", "published_sha256"):
            assert re.fullmatch(r"[0-9a-f]{64}", entry[key])
        assert entry["original_sha256"] != entry["published_sha256"]
        raw = (ROOT / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["published_sha256"]
        assert not re.search(rb"/(?:home|Users)/[^/\s\"]+/", raw)
        document = json.loads(raw)
        pointers = entry["changed_json_pointers"]
        assert pointers and len(pointers) == len(set(pointers))
        for pointer in pointers:
            assert pointer.startswith("/")
            value = document
            for part in pointer[1:].split("/"):
                part = part.replace("~1", "/").replace("~0", "~")
                value = value[int(part)] if isinstance(value, list) else value[part]
            assert isinstance(value, str) and "${WORKSHOP_ROOT}" in value
        assert raw.count(b"${WORKSHOP_ROOT}") == entry["replacement_count"]


def test_historical_training_bindings_identify_originals_not_public_copies():
    entries = {
        entry["path"]: entry
        for entry in json.loads(MANIFEST.read_text())["files"]
    }
    for prefix, admission_name in (
        ("", "admission.json"),
        ("attempt01_", "attempt01_incomplete_admission.json"),
    ):
        relative = f"provenance/student_policy/{prefix}training_receipt.json"
        entry = entries[relative]
        policy_path = ROOT / f"provenance/student_policy/{prefix}policy_manifest.json"
        policy = json.loads(policy_path.read_text())
        assert policy["training_receipt"]["sha256"] == entry["original_sha256"]
        assert policy["training_receipt"]["sha256"] != entry["published_sha256"]
        admission = json.loads((ROOT / "provenance/student_policy" / admission_name).read_text())
        assert admission["manifest_sha256"] == hashlib.sha256(policy_path.read_bytes()).hexdigest()
    first = json.loads(
        (ROOT / "provenance/student_policy/attempt01_incomplete_admission.json").read_text()
    )
    assert first["passed"] is False


@pytest.mark.parametrize("prefix", ["", "attempt01_"])
def test_runtime_artifact_check_rejects_redacted_training_copies(prefix):
    from microduck_workshop.policy.student import checked_artifact

    directory = ROOT / "provenance/student_policy"
    policy = json.loads((directory / f"{prefix}policy_manifest.json").read_text())
    # The attempt snapshot has a publication filename prefix, unlike the raw bundle.
    entry = dict(policy["training_receipt"], path=f"{prefix}training_receipt.json")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        checked_artifact(directory, entry)


def test_publication_metadata_does_not_disclose_private_checkout_prefixes():
    for path in (MANIFEST, ROOT / "provenance/student_policy/README.md"):
        assert not re.search(rb"/(?:home|Users)/[^/\s\"]+/", path.read_bytes())
    readme = (ROOT / "provenance/student_policy/README.md").read_text()
    assert "NONDEPLOYABLE" in readme
    assert "not byte-identical raw receipts" in readme
    assert "cannot bypass artifact or source validation" in readme
