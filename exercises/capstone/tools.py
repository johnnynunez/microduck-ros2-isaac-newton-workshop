"""Focused student implementation; never return success to hide a missing TODO."""


def translate_observation(raw, *, episode_id, frame_id, round_trip_s=0.0):
    """TODO 1: translate the Observe.srv response into sensor-only model input.

    - Check expected episode/frame, strict nonnegative generation and frame sequence.
    - Validate finite nonnegative sim time, age and RPC round trip.
    - Effective age is capture age PLUS the entire round trip; maximum 0.5 seconds.
    - Only genuine fresh observations may retain bounded integer tag IDs.
    - STOP tag 1 overrides GO tag 0; absent/stale/foreign => UNKNOWN, no motion.
    - Construct a NEW allowlisted dict. Never copy raw reason, pose, map or metadata.

    Contract examples and the exact result keys are in tests/test_agent_observation.py.
    Run scripts/agent_check_exercise.py to test this file without a model or ROS.
    """
    raise NotImplementedError("TODO 1: implement sensor-only observation translation")


def walk_bounded(domain, args):
    """TODO 2: validate one bounded request, then use the instructor-owned dispatch.

    Require exactly vx/vy/wz/duration_s; instantiate the shared MotionCommand with
    validation-only identity to reject booleans, strings, nonfinite numbers and bounds.
    Do NOT clip. Forward the validated numeric values to domain.walk_bounded().
    That instructor method re-reads perception AFTER inference, binds episode/generation,
    generates a fresh UUID, checks freshness at ROS send, dispatches ONCE and queries the
    actual independent verdict. Return its receipt unchanged; never fabricate success.
    Never call gateway.bounded_motion directly, auto-reset, or retry an exception.

    Your validation does not replace the instructor's final gate or server watchdog.
    """
    raise NotImplementedError("TODO 2: implement the bounded-motion tool handler")
