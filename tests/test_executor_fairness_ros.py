"""Real rclpy/rmw regression: native wakeups with no dispatchable work.

Wakeups are not a promise of work: a custom waitable may invalidate work after
triggering its guard. This fixture uses real native guard conditions / rcl_wait,
not fabricated wait-set return values. DDS matched events are also exercised.
Run in the pinned ROS image; no simulator/GPU is needed.
"""
import json
import threading
import time
from itertools import pairwise

import pytest

rclpy = pytest.importorskip('rclpy')
from rclpy.callback_groups import MutuallyExclusiveCallbackGroup
from rclpy.event_handler import PublisherEventCallbacks
from rclpy.executors import MultiThreadedExecutor
from rclpy.guard_condition import GuardCondition
from rclpy.node import Node
from rclpy.waitable import NumberOfEntities, Waitable
from std_msgs.msg import String


class InvalidatedWake(Waitable):
    """A real guard wake whose application work was cancelled before dispatch."""
    def __init__(self, context):
        super().__init__(MutuallyExclusiveCallbackGroup())
        self.guard = GuardCondition(None, None, context=context)
        self.wakes = 0

    def __enter__(self):
        self.guard.handle.__enter__()

    def __exit__(self, *args):
        self.guard.handle.__exit__(*args)

    def get_num_entities(self):
        return NumberOfEntities(num_gcs=1)

    def add_to_wait_set(self, wait_set):
        self.index = wait_set.add_guard_condition(self.guard.handle)
        self.guard.trigger()

    def is_ready(self, wait_set):
        assert wait_set.is_ready('guard_condition', self.index)
        self.wakes += 1
        return False

    def take_data(self):
        raise AssertionError('Invalidated work must never dispatch')

    async def execute(self, taken_data):
        raise AssertionError('Invalidated work must never execute')


@pytest.mark.ros
def test_empty_ready_iterations_preserve_independent_renewal():
    rclpy.init()
    node = Node('executor_fairness_regression')
    executor = MultiThreadedExecutor(num_threads=6)
    wake = InvalidatedWake(node.context)
    node.add_waitable(wake)
    matched = []
    node.create_publisher(String, 'fairness_events', 10, event_callbacks=PublisherEventCallbacks(
        matched=lambda event: matched.append(event.current_count)))
    node.create_subscription(String, 'fairness_events', lambda msg: None, 10)
    executor.add_node(node)
    done = threading.Event()
    renewed = [time.monotonic()]

    def renew():
        while not done.wait(.05):
            renewed.append(time.monotonic())

    worker = threading.Thread(target=renew)
    worker.start()
    began = time.monotonic()
    try:
        # No GIL switch-interval changes, sleeps in executor, or fake rcl_wait.
        while time.monotonic() - began < 3:
            executor.spin_once(timeout_sec=.6)
    finally:
        renewed.append(time.monotonic())
        done.set()
        worker.join()
        executor.shutdown()
        node.remove_waitable(wake)
        wake.guard.destroy()
        node.destroy_node()
        rclpy.shutdown()
    gaps = [b-a for a,b in pairwise(renewed)]
    print(json.dumps({'wakes':wake.wakes, 'renewals':len(renewed),
                      'max_renewal_gap_s':max(gaps), 'matched':matched}), flush=True)
    assert wake.wakes > 100, 'must exercise repeated real no-work wakeups'
    assert any(count > 0 for count in matched), 'real DDS event must remain dispatchable'
    # A 50 ms renewer must not miss a whole renewal opportunity. This is
    # deliberately stricter than the production 500 ms lease, never an extension.
    assert max(gaps) < .1, 'no-work executor loop starved independent renewal'
