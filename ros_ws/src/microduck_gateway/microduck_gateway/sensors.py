"""Validate real Lab telemetry without adding pose or other privileged state."""
import time
from microduck_workshop.contracts import finite_number


def checked_state(raw, episode, now=None):
    now = time.monotonic() if now is None else now
    if raw['episode_id'] != episode or not 0 <= now - finite_number(raw['capture_monotonic_s'], 'capture') <= .5:
        raise ValueError('stale or unknown state epoch')
    finite_number(raw['sim_time'], 'sim_time')
    names = raw['joint_names']
    if len(names) != 14 or len(set(names)) != 14:
        raise ValueError('expected 14 unique policy encoder names')
    for key in ('joint_position', 'joint_velocity'):
        if len(raw[key]) != 14:
            raise ValueError('joint array mismatch')
        for value in raw[key]:
            finite_number(value, key)
    imu = raw['imu']
    for key in ('angular_velocity', 'linear_acceleration'):
        if len(imu[key]) != 3:
            raise ValueError('IMU vector mismatch')
        for value in imu[key]:
            finite_number(value, key)
    result = {key: raw[key] for key in ('episode_id', 'sequence', 'sim_time', 'capture_monotonic_s', 'joint_names', 'joint_position', 'joint_velocity')}
    result['imu'] = {key: imu[key] for key in ('angular_velocity', 'linear_acceleration')}
    return result


def checked_calibration(raw):
    for name in ('width', 'height'):
        if type(raw[name]) is not int or not 0 < raw[name] <= 4096:
            raise ValueError('invalid teaching camera dimensions')
    if raw['encoding'] != 'rgb8' or raw['distortion_model'] != 'plumb_bob':
        raise ValueError('unsupported teaching camera calibration')
    if not isinstance(raw['frame_id'], str) or not 0 < len(raw['frame_id']) <= 128:
        raise ValueError('invalid optical frame')
    for name, length in (('k', 9), ('d', 5), ('r', 9), ('p', 12)):
        if len(raw[name]) != length:
            raise ValueError('invalid camera matrix length')
        for value in raw[name]:
            finite_number(value, name)
    if raw['k'][0] <= 0 or raw['k'][4] <= 0 or any(raw['d']):
        raise ValueError('requires positive focal lengths and distortion-free pinhole')
    return {key: raw[key] for key in ('width', 'height', 'frame_id', 'encoding', 'distortion_model', 'k', 'd', 'r', 'p')}
