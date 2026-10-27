"""CPU scheduling/provenance tests. No live DDS latency or physics claim."""
import pytest
from test_ros_gateway import SimFixture
from microduck_gateway.core import Gateway
from microduck_gateway.perception import CaptureCache


class StepFixture(SimFixture):
    def __init__(self):
        super().__init__()
        self.proofs = []

    def post(self, path, body, token=None, *, observation_headers=None):
        self.proofs.append((path, observation_headers))
        if path == '/v1/step':
            result = super().post('/v1/command', body, token)
            self.calls[-1] = (path, body, token)
            return result
        return super().post(path, body, token)


def setup(age=.01, tags=(0,)):
    now = [100.]
    cache = CaptureCache(clock=lambda: now[0])
    cache.record('ep1', 7, 1., now[0] - age, 'camera')
    cache.detect(1., 'camera', tags)
    sim = StepFixture()
    gateway = Gateway(sim, captures=cache)
    gateway.claim()
    return now, cache, sim, gateway


def command(**kwargs):
    return dict(episode_id='ep1', request_id='step1', expected_generation=0,
                vx=.1, vy=0, wz=0, duration_s=2) | kwargs


def test_dds_queued_until_capture_expires_rejected_at_server():
    now, cache, sim, gateway = setup(age=.46)
    assert cache.observe('ep1', 0)['fresh']
    now[0] += .06  # already sent, DDS/server callback scheduling delay
    result = gateway.step_forward(command())
    assert not result['accepted']
    assert not any(path == '/v1/step' for path, *_ in sim.calls)


def test_step_carries_original_capture_deadline_not_receipt_time():
    now, cache, sim, gateway = setup(age=.46)
    assert gateway.step_forward(command())['accepted']
    path, headers = sim.proofs[-1]
    assert path == '/v1/step'
    assert headers == {
        'X-Workshop-Observation-Episode': 'ep1',
        'X-Workshop-Observation-Sequence': '7',
        'X-Workshop-Observation-Deadline': str(cache.latest['capture'] + .5),
    }
    assert float(headers['X-Workshop-Observation-Deadline']) == pytest.approx(100.04)
    assert sim.calls[-1] == ('/v1/step', command(), 'secret')


@pytest.mark.parametrize('tags', [(), (1,), (0, 1)])
def test_server_requires_go_without_stop(tags):
    _, _, sim, gateway = setup(tags=tags)
    assert not gateway.step_forward(command())['accepted']
    assert not any(path == '/v1/step' for path, *_ in sim.calls)


def test_no_capture_source_never_admits_step():
    gateway = Gateway(StepFixture())
    gateway.claim()
    assert not gateway.step_forward(command())['accepted']


@pytest.mark.parametrize('change', [dict(vx=0), dict(vx=.001), dict(wz=.1), dict(duration_s=.5)])
def test_service_rejects_non_step_body(change):
    _, _, sim, gateway = setup()
    assert not gateway.step_forward(command(**change))['accepted']
    assert not any(path == '/v1/step' for path, *_ in sim.calls)


def test_duplicate_capture_cannot_refresh_deadline():
    now, cache, sim, gateway = setup(age=.2)
    assert gateway.step_forward(command())['accepted']
    initial = sim.proofs[-1][1]
    now[0] += .2
    cache.record('ep1', 7, 1., now[0], 'camera')  # reread same image, NOT a new capture
    assert cache.detect(1., 'camera', [0])
    gateway.renew_once()
    assert sim.proofs[-1] == ('/v1/renew', initial)
    now[0] += .11
    gateway.renew_once()
    assert gateway.stopped and sim.calls[-1][0] == '/v1/stop'


@pytest.mark.parametrize('failure', ['stale', 'stop', 'absent', 'foreign'])
def test_active_renewal_requires_current_capture_proof_or_priority_stop(failure):
    now, cache, sim, gateway = setup()
    assert gateway.step_forward(command())['accepted']
    gateway.renew_once()
    original = sim.proofs[-1][1]
    assert original['X-Workshop-Observation-Sequence'] == '7'
    now[0] += .1
    cache.record('ep1', 8, 1.1, now[0], 'camera')
    cache.detect(1.1, 'camera', [0])
    gateway.renew_once()
    assert sim.proofs[-1][1]['X-Workshop-Observation-Sequence'] == '8'
    assert float(sim.proofs[-1][1]['X-Workshop-Observation-Deadline']) == now[0] + .5
    if failure == 'stale':
        now[0] += .51
    elif failure == 'stop':
        cache.detect(1.1, 'camera', [0, 1])
    elif failure == 'absent':
        cache.detect(1.1, 'camera', [])
    else:
        cache.record('foreign', 9, 1.2, now[0], 'camera')
        cache.detect(1.2, 'camera', [0])
    renewals = sum(path == '/v1/renew' for path, *_ in sim.calls)
    gateway.renew_once()
    assert gateway.stopped and gateway.token is None
    assert sim.calls[-1][0] == '/v1/stop'
    assert sum(path == '/v1/renew' for path, *_ in sim.calls) == renewals
    # A new GO never revives expired/stopped authority.
    cache.record('ep1', 10, 1.3, now[0], 'camera')
    cache.detect(1.3, 'camera', [0])
    gateway.renew_once()
    assert sum(path == '/v1/renew' for path, *_ in sim.calls) == renewals
