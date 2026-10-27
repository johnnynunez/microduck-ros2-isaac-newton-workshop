"""Causal DDS regression: queued subscription data wakes default QoS events."""
import collections
import json
import threading
import time
from itertools import pairwise

import pytest

rclpy = pytest.importorskip('rclpy')
from rclpy.event_handler import SubscriptionEventCallbacks
from rclpy.executors import MultiThreadedExecutor
from rclpy.impl.implementation_singleton import rclpy_implementation as native
from rclpy.node import Node
from std_msgs.msg import String


@pytest.mark.ros
@pytest.mark.parametrize('events_enabled', [True, False], ids=['actual-default-events', 'causal-control'])
def test_queued_subscription_event_wakes_preserve_renewal(monkeypatch, events_enabled):
    rclpy.init()
    node = Node('queued_subscription_fairness')
    executor = MultiThreadedExecutor(num_threads=6)
    received = []
    sub = node.create_subscription(
        String, 'queued_subscription', lambda msg: received.append(msg.data), 10,
        event_callbacks=SubscriptionEventCallbacks(use_default_callbacks=events_enabled))
    pub = node.create_publisher(String, 'queued_subscription', 10)
    executor.add_node(node)
    deadline = time.monotonic() + 2
    while not pub.get_subscription_count() and time.monotonic() < deadline:
        time.sleep(.01)
    assert pub.get_subscription_count() == 1
    pub.publish(String(data='retained original DDS sample'))
    # Allow delivery before placing the subscription in its normal queued state.
    time.sleep(.05)
    # This is the exact rclpy state between scheduling and worker execution. Do not
    # fake wait return values, toggle readiness flags or replace event handlers.
    handler = executor._make_handler(sub, node, executor._take_subscription)
    stats = collections.Counter()
    original_wait = native.WaitSet.wait

    def observe_wait(wait_set, timeout):
        original_wait(wait_set, timeout)
        ready = tuple(len(wait_set.get_ready_entities(kind)) for kind in
                      ('subscription', 'guard_condition', 'timer', 'client', 'service'))
        # Unlike the earlier investigation, include actual native QoS event readiness.
        events = sum(wait_set.is_ready('event', wt._event_index) for wt in node.waitables)
        stats[ready + (events,)] += 1

    monkeypatch.setattr(native.WaitSet, 'wait', observe_wait)
    done = threading.Event()
    renewed = [time.monotonic()]

    def renew():
        while not done.wait(.05):
            renewed.append(time.monotonic())

    worker = threading.Thread(target=renew)
    worker.start()
    started = time.monotonic()
    try:
        while time.monotonic() - started < 3:
            executor.spin_once(timeout_sec=.6)
    finally:
        renewed.append(time.monotonic())
        done.set()
        worker.join()
        # Execute the actual pending callback; sample identity must survive.
        handler()
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()
    empty = stats[(0, 0, 0, 0, 0, 0)]
    maximum = max(b-a for a,b in pairwise(renewed))
    print(json.dumps({'events_enabled': events_enabled, 'empty_including_events': empty,
                      'max_renewal_gap_s': maximum, 'renewals': len(renewed),
                      'waits': [(str(k), v) for k,v in stats.items()]}), flush=True)
    assert received == ['retained original DDS sample']
    if events_enabled:
        assert empty > 100, 'must reproduce native empty returns, including empty event readiness'
    else:
        assert empty < 10, 'removing only default subscription events must remove the wake source'
    # Strict fairness budget: production wall lease stays .5 s, not widened.
    assert maximum < .1, 'DDS event-induced no-work spin starved independent renewal'
