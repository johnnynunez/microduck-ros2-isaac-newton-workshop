"""CPU numerical/optimizer tests; never physical admission evidence."""

import os
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("onnx")

ASSET = Path(os.environ.get("MICRODUCK_PUBLIC_ONNX", ".cache/assets/policies/velstand.onnx"))
pytestmark = pytest.mark.skipif(not ASSET.is_file(), reason="requires fetched pinned public ONNX")


def test_public_actor_import_matches_real_onnx():
    import torch

    from microduck_workshop.policy import warmstart
    from microduck_workshop.policy.onnx import VelStandPolicy

    torch.set_num_threads(1)
    assert hasattr(warmstart, "import_public_actor"), "missing exact graph importer"
    actor = warmstart.import_public_actor(ASSET)
    original = VelStandPolicy(ASSET)
    inputs = np.random.default_rng(7).normal(0, 0.1, (32, 61)).astype(np.float32)
    inputs[:, 3:6] = (0, 0, -1)
    with torch.no_grad():
        actual = actor(torch.from_numpy(inputs)).numpy()
    expected = np.concatenate([original.session.run(None, {"obs": row[None]})[0] for row in inputs])
    np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=2e-5)
    assert not actor.mean.requires_grad and not actor.scale.requires_grad


def test_real_gradients_export_saved_updated_actor(tmp_path):
    import onnxruntime as ort
    import torch

    from microduck_workshop.policy.warmstart import export_checkpoint, import_public_actor
    from microduck_workshop.sim.ppo import PPO

    torch.set_num_threads(1)
    torch.manual_seed(7)
    ppo = PPO(actor=import_public_actor(ASSET), learning_rate=1e-6, initial_std=0.005)
    before = {k: v.clone() for k, v in ppo.model.actor.state_dict().items()}
    obs = torch.zeros(32, 61)
    obs[:, 5] = -1
    with torch.no_grad():
        actions, logp, values = ppo.sample(obs)
    result = ppo.update(
        obs, actions, logp, returns=values + 1, advantages=torch.linspace(-1, 1, 32)
    )
    assert result["actor_weight_delta_l2"] > 0
    assert any(not torch.equal(before[k], v) for k, v in ppo.model.actor.state_dict().items())
    ppo.save(tmp_path / "checkpoint.pt", metadata={"actor_init": "public_v8_actor_only"})
    export_checkpoint(tmp_path / "checkpoint.pt", tmp_path / "actor.onnx", source_onnx=ASSET)
    session = ort.InferenceSession(str(tmp_path / "actor.onnx"), providers=["CPUExecutionProvider"])
    expected = ppo.model.actor(obs[:1]).detach().numpy()
    np.testing.assert_allclose(
        session.run(None, {"obs": obs[:1].numpy()})[0], expected, rtol=2e-5, atol=2e-5
    )


def test_checkpoint_loader_never_unpickles_arbitrary_objects(tmp_path):
    import torch

    from microduck_workshop.policy.warmstart import export_checkpoint

    payload = tmp_path / "unsafe.pt"
    torch.save({"model": object()}, payload)
    with pytest.raises(Exception, match="Weights only load failed"):
        export_checkpoint(payload, tmp_path / "actor.onnx", source_onnx=ASSET)
    assert not (tmp_path / "actor.onnx").exists()


def test_import_rejects_unpinned_graph(tmp_path):
    from microduck_workshop.policy.warmstart import import_public_actor

    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"not the pinned graph")
    with pytest.raises(ValueError, match="hash"):
        import_public_actor(bad)


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """CPU optimizer fixture, explicitly not a native admission receipt."""
    import torch

    from microduck_workshop.policy.student import create_manifest, sha256, write_json
    from microduck_workshop.policy.warmstart import export_checkpoint, import_public_actor
    from microduck_workshop.sim.ppo import PPO

    # Isolate constructor/graph tests from native-training evidence validation.
    # This labelled CPU fixture must never claim native updates. The real-path
    # metadata and serving regressions run separately without this patch.
    monkeypatch.setattr(
        "microduck_workshop.policy.student.validate_training_receipt", lambda *args: None
    )
    torch.set_num_threads(1)
    torch.manual_seed(7)
    ppo = PPO(actor=import_public_actor(ASSET), learning_rate=1e-6, initial_std=0.005)
    obs = torch.zeros(8, 61)
    obs[:, 5] = -1
    with torch.no_grad():
        action, logp, value = ppo.sample(obs)
    ppo.update(obs, action, logp, returns=value + 1, advantages=torch.arange(8).float())
    ppo.save(tmp_path / "checkpoint.pt", metadata={"fixture": True})
    export_checkpoint(tmp_path / "checkpoint.pt", tmp_path / "actor.onnx", source_onnx=ASSET)
    write_json(
        tmp_path / "training_receipt.json",
        {
            "evidence_kind": "CPU_UNIT_FIXTURE_NOT_NATIVE",
            "export_parity": {"atol": 2e-5, "rtol": 2e-5},
            "actor_changed_parameters": 1,
            "saved_optimizer_steps": ppo.optimizer_steps,
            "checkpoint_sha256": sha256(tmp_path / "checkpoint.pt"),
            "actor_sha256": sha256(tmp_path / "actor.onnx"),
        },
    )
    create_manifest(tmp_path, mode="training")
    return tmp_path


def test_selected_student_is_actual_export_and_unadmitted_serve_refuses(bundle):
    from microduck_workshop.policy.student import select_student, sha256

    kwargs = {"policy_mode": "training", "command_profile": "direct", "step_profile": "disabled"}
    policy, profile, step = select_student(
        bundle / "policy_manifest.json", mode="validate", **kwargs
    )
    assert policy.sha256 == sha256(bundle / "actor.onnx")
    assert profile.receipt()["policy_sha256"] == policy.sha256 and step is None
    with pytest.raises(ValueError, match="admission"):
        select_student(bundle / "policy_manifest.json", mode="serve", **kwargs)
    with pytest.raises(ValueError, match="substitution"):
        select_student(
            bundle / "policy_manifest.json", mode="validate", candidate_validation=True, **kwargs
        )


@pytest.mark.parametrize("filename", ["actor.onnx", "checkpoint.pt", "training_receipt.json"])
def test_manifest_rejects_each_modified_artifact(bundle, filename):
    from microduck_workshop.policy.student import load_manifest

    path = bundle / filename
    path.write_bytes(path.read_bytes() + b"changed")
    with pytest.raises(ValueError, match="hash"):
        load_manifest(bundle / "policy_manifest.json")


def test_manifest_rejects_control_source_drift(bundle):
    from microduck_workshop.policy.student import load_manifest, read_json, write_json

    path = bundle / "policy_manifest.json"
    data = read_json(path)
    data["source_sha256"]["sim/evaluate.py"] = "0" * 64
    write_json(path, data)
    with pytest.raises(ValueError, match="source"):
        load_manifest(path)


@pytest.mark.parametrize("corruption", ["shape", "nonfinite"])
def test_hash_bound_but_invalid_onnx_is_rejected(bundle, corruption):
    import onnx
    from onnx import numpy_helper

    from microduck_workshop.policy.student import (
        StudentPolicy,
        create_manifest,
        read_json,
        sha256,
        write_json,
    )

    path = bundle / "actor.onnx"
    graph = onnx.load(path)
    if corruption == "shape":
        graph.graph.input[0].type.tensor_type.shape.dim[1].dim_value = 60
    else:
        tensor = graph.graph.initializer[0]
        values = numpy_helper.to_array(tensor).copy()
        values.flat[0] = np.nan
        tensor.CopyFrom(numpy_helper.from_array(values, tensor.name))
    onnx.save(graph, path)
    receipt = read_json(bundle / "training_receipt.json")
    receipt["actor_sha256"] = sha256(path)
    write_json(bundle / "training_receipt.json", receipt)
    create_manifest(bundle, mode="training")
    with pytest.raises(Exception, match="shape|dimension|nonfinite|Gemm"):
        StudentPolicy(bundle / "policy_manifest.json")
