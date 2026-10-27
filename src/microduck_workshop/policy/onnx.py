"""Real pinned VelStand inference. One session, embedded graph normalization."""

import hashlib
from pathlib import Path

import numpy as np

from .contract import HOME, POLICY_SHA256, observation, targets, vector


class VelStandPolicy:
    def __init__(self, path, *, mode="training"):
        import onnxruntime as ort

        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest != POLICY_SHA256:
            raise ValueError(f"public v8 policy hash mismatch: {digest}")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(
            str(path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        ins, outs = self.session.get_inputs(), self.session.get_outputs()
        if (
            len(ins) != 1
            or ins[0].name != "obs"
            or ins[0].shape != [1, 61]
            or ins[0].type != "tensor(float)"
        ):
            raise ValueError("unexpected ONNX input contract")
        if len(outs) != 1 or outs[0].name != "actions" or outs[0].shape != [1, 14]:
            raise ValueError("unexpected ONNX output contract")
        self.mode = mode
        self.sha256 = digest
        self.previous_raw = np.zeros(14, dtype=np.float32)
        self.previous_target = HOME.copy()

    def step(self, **sensors_and_command):
        obs = observation(previous_raw=self.previous_raw, **sensors_and_command)
        raw = vector(self.session.run(["actions"], {"obs": obs})[0][0], 14, "ONNX action")
        target = targets(raw, mode=self.mode, previous_target=self.previous_target)
        self.previous_raw = raw.copy()
        self.previous_target = target.copy()
        return target, {
            "observation": obs[0].tolist(),
            "raw_action": raw.tolist(),
            "target": target.tolist(),
            "mode": self.mode,
            "policy_sha256": self.sha256,
        }
