"""CPU-only causal scheduling regression; not physical/perception acceptance."""
import threading

from microduck_gateway.core import Gateway
from microduck_gateway.perception import CaptureCache

from microduck_workshop.contracts import MotionCommand
from microduck_workshop.policy.step import StepProfile
from microduck_workshop.sim.intent import IntentOwner, ObservationProof


class NativeTransport:
    def __init__(self, owner):
        self.owner = owner
        self.fresh_renewed = threading.Event()

    def get(self, path):
        assert path == '/v1/health'
        return {'protocol_version': 1, 'physics': 'newton', 'ready': True}

    def post(self, path, body, token=None, *, observation_headers=None):
        h = observation_headers
        proof = None if h is None else ObservationProof(
            h['X-Workshop-Observation-Episode'],
            int(h['X-Workshop-Observation-Sequence']),
            float(h['X-Workshop-Observation-Deadline']),
        )
        if path == '/v1/claim':
            return self.owner.claim(body['owner_id'])
        if path == '/v1/step':
            return self.owner.submit_step(MotionCommand.from_dict(body), token, proof)
        if path == '/v1/renew':
            result = self.owner.renew(body['episode_id'], token, proof)
            if proof is not None and proof.sequence == 2:
                self.fresh_renewed.set()
            return result
        if path == '/v1/stop':
            return self.owner.stop(body['episode_id'], latch=body['latch'])
        raise AssertionError(path)


def test_new_go_proof_wakes_renewer_before_old_capture_deadline():
    now = [100.]
    owner = IntentOwner('ep', clock=lambda: now[0], step_profile=StepProfile())
    cache = CaptureCache(clock=lambda: now[0])
    transport = NativeTransport(owner)
    gateway = Gateway(transport, captures=cache)
    gateway.claim()
    cache.record('ep', 1, 0., now[0], 'camera')
    assert gateway.detect(0., 'camera', [0])
    assert gateway.step_forward(MotionCommand('ep', 'step', 0, .1, 0., 0., 2.).as_dict())['accepted']
    assert owner.consume(sim_time=0.) == (.1, 0., 0.)
    # Live failure: periodic renewal preserves an almost-expired ORIGINAL proof.
    now[0] = 100.408
    gateway.renew_once()
    assert owner._pending.proof.deadline == 100.5
    assert owner.consume(sim_time=.05) == (.1, 0., 0.)  # native heartbeat stays live
    # Suppress periodic ticks to prove new evidence itself wakes the worker.
    gateway.start_renewal(interval=10.)
    try:
        now[0] = 100.45
        cache.record('ep', 2, .1, now[0], 'camera')
        assert gateway.detect(.1, 'camera', [0])
        assert transport.fresh_renewed.wait(1.), 'fresh GO remained local until the next periodic renewal'
        assert owner._pending.proof == ObservationProof('ep', 2, 100.95)
        now[0] = 100.51
        assert owner.consume(sim_time=.1) == (.1, 0., 0.)
        # The NEW capture deadline still expires normally; no deadline extension.
        now[0] = 100.951
        owner.watchdog()
        assert owner.status('step')['status'] == 'expired'
        assert owner.status('step')['reason'] == 'observation proof expired'
    finally:
        gateway.close()
    assert not gateway.renew_thread.is_alive()
