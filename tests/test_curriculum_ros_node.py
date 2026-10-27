"""CPU-only adapter tests using explicit fake ROS modules, NOT a ROS smoke test."""

from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace

import pytest

SOLUTION = Path(__file__).resolve().parents[1] / "solutions/ros_basics/joint_watch.py"


def test_helpers_import_without_ros(monkeypatch):
    monkeypatch.setitem(sys.modules, "rclpy", None)
    monkeypatch.setitem(sys.modules, "sensor_msgs", None)
    loaded = runpy.run_path(str(SOLUTION))
    assert callable(loaded["run"])


@pytest.mark.parametrize("invalid", [False, True])
def test_read_only_ros_adapter_wiring_and_cleanup(monkeypatch, invalid):
    events = {"logs": [], "warnings": []}
    msg = SimpleNamespace(
        name=["left_knee"], position=[float("nan") if invalid else -0.1],
        header=SimpleNamespace(stamp=SimpleNamespace(sec=1, nanosec=0)),
    )

    class FakeNode:
        def __init__(self, name):
            events["node_name"] = name

        def declare_parameter(self, name, default):
            return SimpleNamespace(value=default)

        def create_subscription(self, msg_type, topic, callback, qos):
            events["subscription"] = (msg_type, topic, qos)
            self.callback = callback
            return object()

        def get_clock(self):
            return SimpleNamespace(now=lambda: SimpleNamespace(nanoseconds=1_100_000_000))

        def get_logger(self):
            return SimpleNamespace(info=events["logs"].append, warning=events["warnings"].append)

        def destroy_node(self):
            events["destroyed"] = True

    def spin(node):
        node.callback(msg)
        raise KeyboardInterrupt

    modules = {name: ModuleType(name) for name in (
        "rclpy", "rclpy.node", "rclpy.qos", "rclpy.executors", "sensor_msgs", "sensor_msgs.msg",
    )}
    modules["rclpy"].init = lambda args=None: events.update(args=args)
    modules["rclpy"].spin = spin
    modules["rclpy"].try_shutdown = lambda: events.update(shutdown=True)
    modules["rclpy.node"].Node = FakeNode
    modules["rclpy.qos"].qos_profile_sensor_data = object()
    modules["rclpy.executors"].ExternalShutdownException = type("ExternalShutdownException", (Exception,), {})
    modules["sensor_msgs.msg"].JointState = type("FakeJointState", (), {})
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    runpy.run_path(str(SOLUTION))["run"](args=["--ros-args", "-p", "use_sim_time:=true"])
    assert events["node_name"] == "joint_watch"
    assert events["subscription"] == (
        modules["sensor_msgs.msg"].JointState,
        "/workshop/microduck/joint_states",
        modules["rclpy.qos"].qos_profile_sensor_data,
    )
    assert events["args"] == ["--ros-args", "-p", "use_sim_time:=true"]
    assert events["destroyed"] and events["shutdown"]
    if invalid:
        assert any("discarded" in line for line in events["warnings"])
        assert not any("within_sim_age" in line for line in events["logs"])
    else:
        assert any("left_knee=-0.1000 rad" in line for line in events["logs"])
        assert any("within_sim_age" in line for line in events["logs"])
