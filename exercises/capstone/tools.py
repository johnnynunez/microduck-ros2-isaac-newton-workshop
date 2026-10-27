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


def step_forward(domain, args):
    """TODO 2: validate the fixed-step selector, then use instructor-owned dispatch.

    Accept only {} or {"action":"step_forward"}; reject ALL numeric choices/extra keys.
    Call domain.step_forward(args), which constructs .10/0/0/2.0 for step-forward-v1:
    1s active drive and 1s zero command inside the 2s horizon. It re-reads perception
    AFTER inference, binds episode/generation, generates a UUID and dispatches ONCE
    through the ROS step_forward service. Server capture checks and native deadline
    enforcement remain mandatory; a pre-send check alone is insufficient.
    Return the actual independent verdict unchanged; never fabricate success.
    Never call gateway methods directly, auto-reset, or retry an exception.

    Your validation does not replace the instructor's final gate or server watchdog.
    """
    raise NotImplementedError("TODO 2: implement the fixed forward-step tool handler")
