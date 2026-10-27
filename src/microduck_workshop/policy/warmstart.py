"""Exact public v8 actor import; normalization frozen, no critic/optimizer resume."""

import hashlib
from pathlib import Path

import torch
from torch import nn

from .contract import POLICY_SHA256


class PublicActor(nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer("mean", torch.zeros(61))
        self.register_buffer("scale", torch.ones(61))
        self.mlp = nn.Sequential(
            nn.Linear(61, 512),
            nn.ELU(),
            nn.Linear(512, 256),
            nn.ELU(),
            nn.Linear(256, 128),
            nn.ELU(),
            nn.Linear(128, 14),
        )

    def forward(self, obs):
        return self.mlp((obs - self.mean) / self.scale)


def import_public_actor(path):
    """Only the inspected, content-pinned Sub/Div/Gemm/ELU graph is supported."""
    import onnx
    from onnx import numpy_helper

    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != POLICY_SHA256:
        raise ValueError("warm-start public v8 hash mismatch")
    graph = onnx.load(path, load_external_data=False).graph
    if [n.op_type for n in graph.node] != [
        "Sub",
        "Div",
        "Gemm",
        "Elu",
        "Gemm",
        "Elu",
        "Gemm",
        "Elu",
        "Gemm",
    ]:
        raise ValueError("unsupported public actor graph")
    values = {t.name: numpy_helper.to_array(t).copy() for t in graph.initializer}
    actor = PublicActor()
    state = {
        "mean": torch.from_numpy(values["obs_normalizer._mean"].reshape(61)),
        "scale": torch.from_numpy(values["onnx::Div_24"].reshape(61)),
    }
    for name in actor.state_dict():
        if name.startswith("mlp."):
            state[name] = torch.from_numpy(values[name])
    if not all(torch.isfinite(x).all() for x in state.values()) or (state["scale"] <= 0).any():
        raise ValueError("nonfinite or invalid public actor parameters")
    actor.load_state_dict(state, strict=True)
    return actor


def export_checkpoint(checkpoint, output, *, source_onnx):
    """Export the SAVED updated weights into the inspected graph, never the seed weights.

    The checkpoint is loaded with the restricted tensor loader. ONNX initializers
    are replaced from its actor state, preserving public normalization semantics.
    """
    import onnx
    from onnx import numpy_helper

    saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
    actor = import_public_actor(source_onnx)
    actor.load_state_dict(
        {k.removeprefix("actor."): v for k, v in saved["model"].items() if k.startswith("actor.")},
        strict=True,
    )
    if not all(torch.isfinite(x).all() for x in actor.state_dict().values()):
        raise ValueError("nonfinite checkpoint actor")
    if (actor.scale <= 0).any():
        raise ValueError("invalid checkpoint normalization")
    graph = onnx.load(source_onnx, load_external_data=False)
    values = {k: v.detach().cpu().numpy() for k, v in actor.state_dict().items()}
    values["obs_normalizer._mean"] = values.pop("mean")[None]
    values["onnx::Div_24"] = values.pop("scale")[None]
    for initializer in graph.graph.initializer:
        initializer.CopyFrom(numpy_helper.from_array(values[initializer.name], initializer.name))
    onnx.checker.check_model(graph)
    onnx.save(graph, output)
    return actor
