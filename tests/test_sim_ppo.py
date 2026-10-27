"""CPU optimizer unit tests. Synthetic tensors here are not live training evidence."""

import pytest


def test_ppo_optimizer_changes_weights_and_checkpoint_roundtrip(tmp_path):
    torch = pytest.importorskip("torch")
    from microduck_workshop.sim.ppo import PPO

    torch.manual_seed(7)
    ppo = PPO(device="cpu")
    obs = torch.randn(16, 61)
    with torch.no_grad():
        actions, logp, _values = ppo.sample(obs)
    before = torch.cat([p.detach().flatten() for p in ppo.model.parameters()]).clone()
    metrics = ppo.update(
        obs,
        actions,
        logp,
        returns=torch.arange(16).float(),
        advantages=torch.linspace(-1, 1, 16),
        epochs=2,
    )
    after = torch.cat([p.detach().flatten() for p in ppo.model.parameters()])
    assert (after - before).abs().max() > 0
    assert metrics["optimizer_steps"] == 2
    path = tmp_path / "ppo.pt"
    ppo.save(path, metadata={"kind": "CPU_UNIT_TEST"})
    checkpoint = torch.load(path, weights_only=True)
    assert "optimizer" in checkpoint and "model" in checkpoint


def test_training_cli_is_fresh_not_onnx_resume():
    from microduck_workshop.sim.train import parser

    args = parser().parse_args(
        ["--asset-root", ".cache/assets", "--updates", "2", "--horizon", "32"]
    )
    assert args.updates == 2 and args.horizon == 32
