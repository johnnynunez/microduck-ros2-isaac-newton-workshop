"""CPU scheduling fixtures using the real gateway/cache/native owner.

Optional ROS tests exercise generated CDR and isolated DDS with fixture inputs.
No real detector, model, physics, or physical-rest acceptance is claimed.
"""
import threading
import time

import pytest
from microduck_gateway.core import Gateway
from microduck_gateway.perception import CaptureCache

from microduck_workshop.contracts import MotionCommand
from microduck_workshop.policy.step import StepProfile
from microduck_workshop.sim.intent import IntentOwner, ObservationProof


class OwnerTransport:
    """In-process transport only; admission/renewal/stop use production ownership."""

    def __init__(self, owner):
        self.owner = owner
        self.paths = []

    def get(self, path):
        if path == '/v1/health':
            return {'protocol_version': 1, 'ready': True, 'physics': 'newton'}
        return self.owner.status(path.removeprefix('/v1/status/'))

    def post(self, path, body, token=None, *, observation_headers=None):
        self.paths.append(path)
        headers = observation_headers
        proof = None if headers is None else ObservationProof(
            headers['X-Workshop-Observation-Episode'],
            int(headers['X-Workshop-Observation-Sequence']),
            float(headers['X-Workshop-Observation-Deadline']),
        )
        if path == '/v1/claim':
            return self.owner.claim(body['owner_id'])
        if path == '/v1/step':
            return self.owner.submit_step(MotionCommand.from_dict(body), token, proof)
        if path == '/v1/renew':
            return self.owner.renew(body['episode_id'], token, proof)
        if path == '/v1/stop':
            return self.owner.stop(body['episode_id'], latch=body['latch'])
        raise AssertionError(path)


@pytest.fixture
def boundary():
    now = [100.]
    owner = IntentOwner('ep', clock=lambda: now[0], step_profile=StepProfile())
    cache = CaptureCache(clock=lambda: now[0])
    transport = OwnerTransport(owner)
    gateway = Gateway(transport, captures=cache)
    gateway.claim()
    cache.record('ep', 1, 0., now[0], 'camera')
    assert cache.detect(0., 'camera', [0])
    return now, owner, cache, transport, gateway


def step(gateway, request_id='step'):
    return gateway.step_forward(MotionCommand(
        'ep', request_id, gateway.generation, .1, 0., 0., 2.,
    ).as_dict())


@pytest.mark.parametrize('tags', [(1,), (0, 1), (), (7,)])
def test_disqualifying_detection_cannot_be_erased_before_renewal(boundary, tags):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    assert owner.consume(sim_time=0.) == (.1, 0., 0.)
    gateway.renew_once()
    now[0] = 100.1
    cache.record('ep', 2, .1, now[0], 'camera')
    assert cache.detect(.1, 'camera', tags)
    assert cache.observe('ep', gateway.generation)['tag_ids'] == list(tags)
    # Revocation occurs at acceptance, even before priority-stop I/O runs.
    assert gateway.stopped and gateway.token is None
    now[0] = 100.2
    cache.record('ep', 3, .2, now[0], 'camera')
    assert cache.detect(.2, 'camera', [0])
    # The latest observation stays truthful; revocation must survive separately.
    assert cache.observe('ep', gateway.generation)['tag_ids'] == [0]
    renewals = transport.paths.count('/v1/renew')
    now[0] = 100.3
    gateway.renew_once()
    assert owner.stop_latched
    assert gateway.stopped and gateway.token is None
    assert owner.consume(sim_time=.3) == (0., 0., 0.)
    assert transport.paths.count('/v1/renew') == renewals
    assert not step(gateway, 'later-go')['accepted']


@pytest.mark.parametrize('tags', [(1,), ()])
def test_real_ros_detection_callback_dispatches_stop_without_renewal(boundary, tags):
    """Generated message CDR + production callback, not DDS or physical evidence."""
    pytest.importorskip('rclpy')
    from types import SimpleNamespace

    from isaac_ros_apriltag_interfaces.msg import AprilTagDetection, AprilTagDetectionArray
    from microduck_gateway.node import GatewayNode
    from rclpy.serialization import deserialize_message, serialize_message

    now, owner, cache, _, gateway = boundary
    assert step(gateway)['accepted']
    assert owner.consume(sim_time=0.) == (.1, 0., 0.)
    now[0] = 100.1
    cache.record('ep', 2, .1, now[0], 'camera')
    message = AprilTagDetectionArray()
    message.header.frame_id = 'camera'
    message.header.stamp.nanosec = 100_000_000
    message.detections = [AprilTagDetection(id=tag) for tag in tags]
    message = deserialize_message(serialize_message(message), AprilTagDetectionArray)
    # Do not construct a node/start services: call the real method with its
    # production cache and gateway dependencies, using the generated ROS types.
    receiver = SimpleNamespace(captures=cache, gateway=gateway)
    GatewayNode.detection(receiver, message)
    assert owner.stop_latched
    assert gateway.stopped and gateway.token is None
    assert owner.consume(sim_time=.1) == (0., 0., 0.)


@pytest.mark.parametrize('tags', [(1,), ()])
def test_detection_overtakes_pending_command_ack(boundary, tags):
    now, owner, cache, transport, gateway = boundary
    entered, release = threading.Event(), threading.Event()
    original = transport.post

    def delayed_ack(path, body, token=None, *, observation_headers=None):
        result = original(path, body, token, observation_headers=observation_headers)
        if path == '/v1/step':
            entered.set()
            assert release.wait(2)
        return result

    transport.post = delayed_ack
    results = []
    sender = threading.Thread(target=lambda: results.append(step(gateway)))
    sender.start()
    try:
        assert entered.wait(1)
        assert gateway.pending
        assert owner.consume(sim_time=0.) == (.1, 0., 0.)
        now[0] = 100.1
        cache.record('ep', 2, .1, now[0], 'camera')
        assert gateway.detect(.1, 'camera', tags)
        assert owner.stop_latched and gateway.stopped
        assert owner.consume(sim_time=.1) == (0., 0., 0.)
        now[0] = 100.2
        cache.record('ep', 3, .2, now[0], 'camera')
        assert gateway.detect(.2, 'camera', [0])
        gateway.renew_once()
        assert transport.paths.count('/v1/stop') == 1
        assert '/v1/renew' not in transport.paths
    finally:
        release.set()
        sender.join(2)
    assert not sender.is_alive()
    assert results[0]['status'] == 'superseded_by_stop'
    assert not results[0]['accepted']
    assert not step(gateway, 'new-go')['accepted']


@pytest.mark.parametrize('case', [
    'wrong-frame', 'unmatched-stamp', 'stale', 'future', 'regressing', 'foreign',
])
def test_rejected_or_foreign_stop_cannot_manufacture_revocation(boundary, case):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    now[0] = 100.1
    if case == 'wrong-frame':
        accepted = gateway.detect(0., 'not-camera', [1])
    elif case == 'unmatched-stamp':
        accepted = gateway.detect(99., 'camera', [1])
    else:
        episode = 'foreign' if case == 'foreign' else 'ep'
        sequence = 0 if case == 'regressing' else 2
        capture = {'stale': 99.5, 'future': 100.2}.get(case, now[0])
        cache.record(episode, sequence, .1, capture, 'camera')
        accepted = gateway.detect(.1, 'camera', [1])
    assert accepted is (case == 'foreign')
    assert not gateway.stopped and gateway.token is not None
    assert not owner.stop_latched and '/v1/stop' not in transport.paths
    # A foreign record is not STOP evidence for this owner. Restore its own
    # proof before renewing; absent own proof must still fail closed separately.
    if case == 'foreign':
        cache.record('ep', 3, .2, now[0], 'camera')
        assert gateway.detect(.2, 'camera', [0])
    gateway.renew_once()
    assert not gateway.stopped and not owner.stop_latched
    assert owner.consume(sim_time=.1) == (.1, 0., 0.)


def test_stale_proof_revokes_even_with_recent_actuator_renewal(boundary):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    assert owner.consume(sim_time=0.) == (.1, 0., 0.)
    now[0] = 100.4
    gateway.renew_once()  # actuator lease now lasts until 100.9, proof only 100.5
    assert owner.consume(sim_time=.4) == (.1, 0., 0.)
    renewals = transport.paths.count('/v1/renew')
    now[0] = 100.51
    gateway.renew_once()
    assert gateway.stopped and owner.stop_latched
    assert owner.consume(sim_time=.51) == (0., 0., 0.)
    cache.record('ep', 2, .51, now[0], 'camera')
    assert gateway.detect(.51, 'camera', [0])
    gateway.renew_once()
    assert transport.paths.count('/v1/renew') == renewals
    assert not step(gateway, 'new-go')['accepted']


def test_valid_go_control_keeps_original_proof_deadline(boundary):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    now[0] = 100.1
    cache.record('ep', 2, .1, now[0], 'camera')
    assert gateway.detect(.1, 'camera', [0, 7])
    now[0] = 100.2
    gateway.renew_once()
    assert not gateway.stopped and not owner.stop_latched
    assert '/v1/stop' not in transport.paths
    assert float(cache.step_headers('ep')['X-Workshop-Observation-Deadline']) == 100.6
    assert owner.consume(sim_time=.2) == (.1, 0., 0.)


def test_stop_io_does_not_hold_capture_or_admission_lock(boundary):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    entered, release = threading.Event(), threading.Event()
    original = transport.post

    def delayed_stop(path, body, token=None, *, observation_headers=None):
        if path == '/v1/stop':
            entered.set()
            assert release.wait(2)
        return original(path, body, token, observation_headers=observation_headers)

    transport.post = delayed_stop
    now[0] = 100.1
    cache.record('ep', 2, .1, now[0], 'camera')
    receiver = threading.Thread(target=lambda: gateway.detect(.1, 'camera', [1]))
    receiver.start()
    try:
        assert entered.wait(1)
        assert gateway.stopped and gateway.token is None
        # Another callback can acquire both locks while STOP transport waits.
        acquired = gateway.lock.acquire(timeout=.1)
        assert acquired
        if acquired:
            gateway.lock.release()
        now[0] = 100.2
        cache.record('ep', 3, .2, now[0], 'camera')
        assert gateway.detect(.2, 'camera', [0])
        gateway.renew_once()
        assert '/v1/renew' not in transport.paths
        assert not step(gateway, 'new-go')['accepted']
    finally:
        release.set()
        receiver.join(2)
    assert not receiver.is_alive()
    assert owner.stop_latched


@pytest.mark.ros
@pytest.mark.parametrize('tags', [(1,), ()])
def test_real_dds_detection_overtakes_service_ack(monkeypatch, tags):
    """Real DDS and production node; CPU owner/transport and detector-input fixtures."""
    rclpy = pytest.importorskip('rclpy')
    from isaac_ros_apriltag_interfaces.msg import AprilTagDetection, AprilTagDetectionArray
    from microduck_gateway import node as gateway_node
    from microduck_workshop_interfaces.srv import BoundedMotion
    from rclpy.executors import MultiThreadedExecutor

    now = [100.]
    owner = IntentOwner('ep', clock=lambda: now[0], step_profile=StepProfile())
    cache = CaptureCache(clock=lambda: now[0])
    cache.record('ep', 1, 0., now[0], 'camera')
    assert cache.detect(0., 'camera', [0])
    transport = OwnerTransport(owner)
    entered, release, stopped = threading.Event(), threading.Event(), threading.Event()
    original = transport.post

    def delayed_ack(path, body, token=None, *, observation_headers=None):
        result = original(path, body, token, observation_headers=observation_headers)
        if path == '/v1/step':
            entered.set()
            assert release.wait(5)
        elif path == '/v1/stop':
            stopped.set()
        return result

    transport.post = delayed_ack
    monkeypatch.setattr(gateway_node, 'SimHTTP', lambda url: transport)
    monkeypatch.setattr(gateway_node, 'CaptureCache', lambda: cache)
    rclpy.init()
    node = gateway_node.GatewayNode()
    # Freeze renewal scheduling so only the actual detection callback can stop.
    node.gateway.shutdown_event.set()
    node.gateway.renew_thread.join(1)
    for timer in node.timers:
        timer.cancel()
    client = rclpy.create_node('stop_event_cpu_fixture')
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    executor.add_node(client)
    worker = threading.Thread(target=executor.spin)
    worker.start()
    try:
        service = client.create_client(BoundedMotion, '/workshop/microduck/step_forward')
        publisher = client.create_publisher(
            AprilTagDetectionArray, '/workshop/microduck/tag_detections', 10,
        )
        assert service.wait_for_service(timeout_sec=3)
        deadline = time.monotonic() + 3
        while publisher.get_subscription_count() == 0 and time.monotonic() < deadline:
            time.sleep(.01)
        assert publisher.get_subscription_count() > 0
        result = service.call_async(BoundedMotion.Request(
            episode_id='ep', request_id='dds-step', expected_generation=0,
            vx=.1, vy=0., wz=0., duration_s=2.,
        ))
        done = threading.Event()
        result.add_done_callback(lambda future: done.set())
        assert entered.wait(2)
        assert node.gateway.pending and not done.is_set()
        assert owner.consume(sim_time=0.) == (.1, 0., 0.)
        now[0] = 100.1
        cache.record('ep', 2, .1, now[0], 'camera')
        message = AprilTagDetectionArray()
        message.header.frame_id = 'camera'
        message.header.stamp.nanosec = 100_000_000
        message.detections = [AprilTagDetection(id=tag) for tag in tags]
        publisher.publish(message)
        assert stopped.wait(2), 'accepted detection must not wait for renewal or command ACK'
        assert owner.stop_latched and node.gateway.stopped
        assert owner.consume(sim_time=.1) == (0., 0., 0.)
        release.set()
        assert done.wait(2)
        assert not result.result().accepted
        assert result.result().status == 'superseded_by_stop'
    finally:
        release.set()
        executor.shutdown(timeout_sec=3)
        worker.join(3)
        client.destroy_node()
        node.destroy_node()
        rclpy.shutdown()
    assert not worker.is_alive()


def test_detection_without_capture_source_cannot_create_stop():
    now = [100.]
    owner = IntentOwner('ep', clock=lambda: now[0], step_profile=StepProfile())
    transport = OwnerTransport(owner)
    gateway = Gateway(transport)
    gateway.claim()
    assert not gateway.detect(0., 'camera', [1])
    assert not gateway.stopped and '/v1/stop' not in transport.paths


def test_stop_transport_failure_never_rearms_on_new_go(boundary):
    now, owner, cache, transport, gateway = boundary
    assert step(gateway)['accepted']
    assert owner.consume(sim_time=0.) == (.1, 0., 0.)
    original = transport.post

    def fail_stop(path, body, token=None, *, observation_headers=None):
        if path == '/v1/stop':
            raise TimeoutError('CPU transport fixture')
        return original(path, body, token, observation_headers=observation_headers)

    transport.post = fail_stop
    now[0] = 100.1
    cache.record('ep', 2, .1, now[0], 'camera')
    assert gateway.detect(.1, 'camera', [1])
    assert gateway.stopped and gateway.token is None
    now[0] = 100.2
    cache.record('ep', 3, .2, now[0], 'camera')
    assert gateway.detect(.2, 'camera', [0])
    gateway.renew_once()
    assert '/v1/renew' not in transport.paths
    assert not step(gateway, 'new-go')['accepted']
    # Do not claim native stop delivery. The unchanged native deadline expires.
    assert not owner.stop_latched
    now[0] = 100.51
    assert owner.consume(sim_time=.51) == (0., 0., 0.)
