"""Minimal transparent PPO for the short workshop optimizer exercise.

This is a fresh actor+critic+optimizer, not an ONNX resume or a converged gait.
"""

import torch
from torch import nn


class ActorCritic(nn.Module):
    def __init__(self):
        super().__init__()
        self.actor = nn.Sequential(
            nn.Linear(61, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 14)
        )
        self.critic = nn.Sequential(
            nn.Linear(61, 64), nn.Tanh(), nn.Linear(64, 64), nn.Tanh(), nn.Linear(64, 1)
        )
        self.log_std = nn.Parameter(torch.full((14,), -2.3))
        nn.init.orthogonal_(self.actor[-1].weight, gain=0.01)
        nn.init.zeros_(self.actor[-1].bias)

    def distribution(self, obs):
        return torch.distributions.Normal(self.actor(obs), self.log_std.exp())


class PPO:
    def __init__(self, *, device="cpu", learning_rate=3e-4):
        self.device = device
        self.model = ActorCritic().to(device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.optimizer_steps = 0

    def sample(self, obs):
        dist = self.model.distribution(obs)
        action = dist.sample()
        return action, dist.log_prob(action).sum(-1), self.model.critic(obs).squeeze(-1)

    def update(self, obs, actions, old_logp, *, returns, advantages, epochs=4):
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        before = torch.cat([p.detach().flatten() for p in self.model.parameters()]).clone()
        for _ in range(epochs):
            dist = self.model.distribution(obs)
            logp = dist.log_prob(actions).sum(-1)
            ratio = (logp - old_logp).exp()
            surrogate = torch.minimum(ratio * advantages, ratio.clamp(0.8, 1.2) * advantages)
            value = self.model.critic(obs).squeeze(-1)
            value_loss = (value - returns).square().mean()
            policy_loss = -surrogate.mean()
            entropy = dist.entropy().sum(-1).mean()
            loss = policy_loss + 0.5 * value_loss - 0.001 * entropy
            if not torch.isfinite(loss):
                raise RuntimeError("PPO loss became nonfinite")
            self.optimizer.zero_grad(set_to_none=True)
            loss.backward()
            norm = torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            if not torch.isfinite(norm):
                raise RuntimeError("PPO gradient became nonfinite")
            self.optimizer.step()
            self.optimizer_steps += 1
        after = torch.cat([p.detach().flatten() for p in self.model.parameters()])
        delta = float(torch.linalg.vector_norm(after - before))
        if delta <= 0:
            raise RuntimeError("PPO optimizer did not change weights")
        return {
            "policy_loss": float(policy_loss.detach()),
            "value_loss": float(value_loss.detach()),
            "entropy": float(entropy.detach()),
            "weight_delta_l2": delta,
            "gradient_norm": float(norm),
            "optimizer_steps": self.optimizer_steps,
        }

    def save(self, path, *, metadata):
        torch.save(
            {
                "model": self.model.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "optimizer_steps": self.optimizer_steps,
                "metadata": metadata,
            },
            path,
        )
