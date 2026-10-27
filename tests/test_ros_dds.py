"""Actual DDS gate. Run inside built Lyrical image, NOT the host CPU suite.
No fixture publisher or simulated physics success is claimed by this test.
"""
import os
import subprocess
import sys
import time
import pytest
rclpy = pytest.importorskip('rclpy')
from microduck_workshop_interfaces.srv import Observe, BoundedMotion, MotionStatus
from std_srvs.srv import Trigger


def test_real_dds_services_refuse_when_simulator_absent():
    process = subprocess.Popen([sys.executable, '-m', 'microduck_gateway.node', '--ros-args', '-p', 'sim_url:=http://127.0.0.1:18766'])
    rclpy.init()
    node = rclpy.create_node('dds_gate_client')
    try:
        observe = node.create_client(Observe, '/workshop/microduck/observe')
        assert observe.wait_for_service(timeout_sec=15)
        result = observe.call_async(Observe.Request())
        rclpy.spin_until_future_complete(node, result, timeout_sec=5)
        assert result.result() is not None
        assert not result.result().fresh
        assert list(result.result().tag_ids) == []
        motion = node.create_client(BoundedMotion, '/workshop/microduck/bounded_motion')
        assert motion.wait_for_service(timeout_sec=5)
        request = BoundedMotion.Request(episode_id='absent', request_id='dds_probe', expected_generation=0, vx=.05, vy=0., wz=0., duration_s=.2)
        result = motion.call_async(request)
        rclpy.spin_until_future_complete(node, result, timeout_sec=5)
        assert not result.result().accepted
        status = node.create_client(MotionStatus, '/workshop/microduck/motion_status')
        assert status.wait_for_service(timeout_sec=5)
        result = status.call_async(MotionStatus.Request(episode_id='absent', request_id='dds_probe'))
        rclpy.spin_until_future_complete(node, result, timeout_sec=5)
        assert result.result() is not None
        assert not result.result().known
        assert not result.result().verification_available
        assert not result.result().verified
        stop = node.create_client(Trigger, '/workshop/microduck/emergency_stop')
        assert stop.wait_for_service(timeout_sec=5)
        result = stop.call_async(Trigger.Request())
        rclpy.spin_until_future_complete(node, result, timeout_sec=5)
        assert result.result() is not None
        assert not result.result().success  # absent simulator cannot acknowledge stop
    finally:
        node.destroy_node()
        rclpy.shutdown()
        process.terminate()
        assert process.wait(timeout=10) == 0
