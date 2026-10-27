"""CPU fixtures only: not live ROS, physics, or perception evidence."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'ros_ws/src/microduck_gateway'))
import pytest
import threading
import time
from microduck_gateway.core import Gateway


class SimFixture:
    def __init__(self):
        self.calls = []
        self.generation = 0
    def post(self, path, body, token=None):
        self.calls.append((path, body, token))
        if path == '/v1/claim':
            return dict(lease_token='secret', episode_id='ep1', generation=0, lease_timeout_s=.5)
        if path == '/v1/command':
            self.generation += 1
            return dict(accepted=True, episode_id='ep1', request_id=body['request_id'], generation=self.generation, status='accepted', reason='', lease_token='secret', world_pose=[1, 2, 3])
        if path == '/v1/stop':
            self.generation += 1
            return dict(generation=self.generation)
        return {}
    def get(self, path):
        return dict(protocol_version=1, ready=True, physics='newton', episode_id='ep1', generation=self.generation)


def command(**kwargs):
    return dict(episode_id='ep1', request_id='r1', expected_generation=0, vx=.05, vy=0., wz=0., duration_s=.2) | kwargs


def test_command_is_exact_validated_and_redacted():
    sim = SimFixture()
    gateway = Gateway(sim)
    gateway.claim()
    result = gateway.command(command())
    assert result == dict(accepted=True, episode_id='ep1', request_id='r1', generation=1, status='accepted', reason='')
    assert sim.calls[-1] == ('/v1/command', command(), 'secret')
    for bad in (command(vx=float('nan')), command(extra=True), command(expected_generation=0), command(episode_id='old')):
        assert not gateway.command(bad)['accepted']
    assert sum(c[0] == '/v1/command' for c in sim.calls) == 1


def test_priority_stop_overtakes_blocked_command_and_late_ack():
    sim = SimFixture()
    original = sim.post
    entered, release = threading.Event(), threading.Event()
    def blocked(path, body, token=None):
        if path == '/v1/command':
            entered.set()
            assert release.wait(2)
        return original(path, body, token)
    sim.post = blocked
    gateway = Gateway(sim)
    gateway.claim()
    result = []
    worker = threading.Thread(target=lambda: result.append(gateway.command(command())))
    worker.start()
    assert entered.wait(1)
    try:
        assert gateway.stop()['success']
    finally:
        release.set()
        worker.join(2)
    assert result[0]['accepted'] is False
    assert result[0]['status'] == 'superseded_by_stop'
    assert not gateway.command(command(request_id='r2', expected_generation=gateway.generation))['accepted']


def test_uncertain_send_never_retries_and_disarms():
    sim = SimFixture()
    gateway = Gateway(sim)
    gateway.claim()
    def failed(*args):
        raise TimeoutError('private payload must not leak')
    sim.post = failed
    assert gateway.command(command())['status'] == 'delivery_unknown'
    assert gateway.token is None
    assert not gateway.command(command(request_id='r2'))['accepted']


def test_lease_renews_without_model_and_failure_disarms():
    sim = SimFixture()
    gateway = Gateway(sim)
    gateway.claim()
    gateway.start_renewal(interval=.01)
    time.sleep(.05)
    gateway.close()
    assert any(c[0] == '/v1/renew' for c in sim.calls)
    assert gateway.stopped


def test_status_is_allowlisted_and_epoch_checked():
    sim = SimFixture()
    gateway = Gateway(sim)
    gateway.claim()
    sim.get = lambda path: dict(known=True, completed=True, verification_available=False, verified=True, status='completed', reason='', generation=1, episode_id='ep1', world_position=[1, 2, 3], lease_token='secret')
    result = gateway.status('ep1', 'r1')
    assert set(result) == {'known', 'completed', 'verification_available', 'verified', 'status', 'reason', 'generation'}
    assert not result['verified']
    assert not gateway.status('old', 'r1')['known']


def test_failed_renewal_disarms_without_reclaim():
    sim = SimFixture()
    gateway = Gateway(sim)
    gateway.claim()
    sim.post = lambda *args: (_ for _ in ()).throw(TimeoutError())
    gateway.start_renewal(interval=.01)
    time.sleep(.05)
    assert gateway.token is None
    assert gateway.stopped
    gateway.close()


def test_claim_uses_unique_owners_and_mismatched_ack_fails_closed():
    first, second = SimFixture(), SimFixture()
    one, two = Gateway(first), Gateway(second)
    one.claim()
    two.claim()
    assert first.calls[0][1]['owner_id'] != second.calls[0][1]['owner_id']
    first.post = lambda *args: dict(accepted=True, episode_id='wrong', request_id='r1', generation=1, status='accepted', reason='')
    assert one.command(command())['status'] == 'delivery_unknown'
    assert one.token is None
