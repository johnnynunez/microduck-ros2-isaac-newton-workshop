"""CPU-only sensor fixtures. They must never count as live sensor evidence."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1] / 'ros_ws/src/microduck_gateway'))
from microduck_gateway.sensors import checked_state


def state(**kwargs):
    return dict(episode_id='ep', sequence=2, sim_time=1.25, capture_monotonic_s=9.9,
                joint_names=[f'j{i}' for i in range(14)], joint_position=[0.]*14,
                joint_velocity=[0.]*14, imu=dict(angular_velocity=[0., 0., 0.], linear_acceleration=[0., 0., 9.81]), world_pose=[1, 2, 3]) | kwargs


def test_checked_state_only_sensor_fields_and_original_age():
    result = checked_state(state(), 'ep', now=10.)
    assert 'world_pose' not in result
    assert len(result['joint_names']) == 14
    for bad in (state(episode_id='old'), state(capture_monotonic_s=9.), state(joint_position=[0.]), state(sim_time=float('nan')), state(joint_velocity=[float('inf')]*14)):
        with pytest.raises(ValueError):
            checked_state(bad, 'ep', now=10.)
