"""Thread-safe validated intentions. This module never reads or writes physics.

The simulation thread is the only caller of consume(). A watchdog may clear intent
while that thread is paused, so a resumed simulation cannot revive stale motion.
"""

import secrets
import threading
import time
from dataclasses import dataclass

from microduck_workshop.contracts import LEASE_TIMEOUT_S, ContractError, MotionCommand, identifier


@dataclass
class Pending:
    command: MotionCommand
    generation: int
    accepted_wall: float
    start_sim: float | None = None


class IntentOwner:
    def __init__(self, episode_id, *, clock=time.monotonic, command_profile=None, max_records=4096):
        if type(max_records) is not int or max_records < 1:
            raise ValueError("max_records must be a positive integer")
        self.max_records = max_records
        self.command_profile = command_profile
        self.episode_id = identifier(episode_id, "episode_id")
        self.clock = clock
        self.lock = threading.RLock()
        self.generation = 0
        self.stop_latched = False
        self._owner_id = None
        self._token = None
        self._renewed = -float("inf")
        self._simulation_heartbeat = self.clock()
        self._pending = None
        self._records = {}

    def _finish(self, status, reason):
        if self._pending:
            record = self._records[self._pending.command.request_id]
            record.update(status=status, completed=True, reason=reason)
            self._pending = None

    def _expire(self):
        now = self.clock()
        if now - self._renewed >= LEASE_TIMEOUT_S:
            self._finish("expired", "wall lease expired")
            self._owner_id = self._token = None
        # Command duration is simulation time, as transport v1 specifies. A separate
        # native-loop wall heartbeat catches pauses even if the lease renewer lives.
        if self._pending and now - self._simulation_heartbeat >= LEASE_TIMEOUT_S:
            self._finish("expired", "native simulation heartbeat expired")

    def watchdog(self):
        with self.lock:
            self._expire()

    def _lease(self, token):
        self._expire()
        if (
            not isinstance(token, str)
            or self._token is None
            or not secrets.compare_digest(token, self._token)
        ):
            raise ContractError("invalid or expired lease")

    def claim(self, owner_id):
        identifier(owner_id, "owner_id")
        with self.lock:
            self._expire()
            if self.stop_latched:
                raise ContractError("stop is latched; operator reset required")
            if self._owner_id is not None:
                raise ContractError("an unexpired owner already holds the lease")
            self._owner_id = owner_id
            self._token = secrets.token_urlsafe(32)
            self._renewed = self.clock()
            return {
                "lease_token": self._token,
                "episode_id": self.episode_id,
                "generation": self.generation,
                "lease_timeout_s": LEASE_TIMEOUT_S,
            }

    def renew(self, episode_id, token):
        with self.lock:
            if episode_id != self.episode_id:
                raise ContractError("episode mismatch")
            self._lease(token)
            self._renewed = self.clock()
            return {
                "episode_id": self.episode_id,
                "generation": self.generation,
                "lease_timeout_s": LEASE_TIMEOUT_S,
            }

    def submit(self, command, token):
        if not isinstance(command, MotionCommand):
            raise ContractError("expected a validated MotionCommand")
        with self.lock:
            self._lease(token)
            if command.episode_id != self.episode_id:
                raise ContractError("episode mismatch")
            if self.stop_latched:
                raise ContractError("stop is latched")
            if command.expected_generation != self.generation:
                raise ContractError("generation mismatch")
            if command.request_id in self._records:
                raise ContractError("repeated request ID; unknown delivery must not be retried")
            if self._pending is not None:
                raise ContractError("a motion request is already active")
            if self.command_profile is not None:
                self.command_profile.validate_request(command)
            if len(self._records) >= self.max_records:
                raise ContractError("request history capacity reached; operator restart required")
            self.generation += 1
            self._pending = Pending(command, self.generation, self.clock())
            record = {
                "known": True,
                "episode_id": self.episode_id,
                "request_id": command.request_id,
                "generation": self.generation,
                "status": "accepted",
                "completed": False,
                "verification_available": False,
                "verified": False,
                "reason": "queued; no physical verdict",
            }
            self._records[command.request_id] = record
            return {
                k: v
                for k, v in dict(record, accepted=True).items()
                if k in ("accepted", "episode_id", "request_id", "generation", "status", "reason")
            }

    def consume(self, *, sim_time):
        with self.lock:
            self._expire()
            self._simulation_heartbeat = self.clock()
            pending = self._pending
            if self.stop_latched or pending is None:
                return (0.0, 0.0, 0.0)
            if pending.start_sim is None:
                pending.start_sim = sim_time
                self._records[pending.command.request_id]["status"] = "executing"
            if sim_time - pending.start_sim >= pending.command.duration_s:
                self._finish("completed", "intent duration ended; physical verdict pending")
                return (0.0, 0.0, 0.0)
            command = pending.command
            return (command.vx, command.vy, command.wz)

    def stop(self, episode_id, *, latch):
        if latch is not True:
            raise ContractError("stop requires latch=true; only an operator reset can re-arm")
        with self.lock:
            if episode_id != self.episode_id:
                raise ContractError("episode mismatch")
            self.generation += 1
            self.stop_latched = True
            self._finish("stopped", "priority stop; balancing may continue, rest unverified")
            self._owner_id = self._token = None
            return {
                "episode_id": self.episode_id,
                "generation": self.generation,
                "stop_latched": True,
                "status": "stopped",
            }

    def verdict(self, request_id, *, verified, reason):
        """Evaluator-only callback, deliberately not an HTTP endpoint."""
        if type(verified) is not bool:
            raise ValueError("verdict must be boolean")
        with self.lock:
            record = self._records[request_id]
            if not record["completed"]:
                raise ContractError("physical verdict requires a completed request")
            record.update(verification_available=True, verified=verified, reason=reason)

    def status(self, request_id):
        identifier(request_id, "request_id")
        with self.lock:
            self._expire()
            return self._records.get(
                request_id,
                {
                    "known": False,
                    "episode_id": self.episode_id,
                    "request_id": request_id,
                    "generation": self.generation,
                    "status": "unknown",
                    "completed": False,
                    "verification_available": False,
                    "verified": False,
                    "reason": "unknown request ID",
                },
            ).copy()
