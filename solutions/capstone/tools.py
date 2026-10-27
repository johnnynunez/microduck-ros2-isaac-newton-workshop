"""Complete reference solution. Only instructor-owned methods dispatch ROS motion."""

from microduck_workshop.agent.observation import translate_observation as translate_observation
from microduck_workshop.contracts import ContractError, MotionCommand

# Observation reference implementation is the actual production function above, not a
# mock. Its complete readable source is src/microduck_workshop/agent/observation.py.
# Keeping one implementation prevents the teacher and live-agent safety filters drifting.


def walk_bounded(domain, args):
    """Validate a request and faithfully return the instructor's actual ROS receipt."""
    fields = {"vx", "vy", "wz", "duration_s"}
    if not isinstance(args, dict) or set(args) != fields:
        raise ContractError("exactly vx, vy, wz, duration_s are required")
    checked = MotionCommand(domain.episode_id, "validation_only", 0, **args)
    # The instructor path performs the fresh-at-send check and constructs the real UUID
    # and current expected_generation. This validation-only command is NEVER dispatched.
    return domain.walk_bounded({name: getattr(checked, name) for name in fields})
