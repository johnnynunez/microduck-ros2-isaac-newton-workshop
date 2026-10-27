"""Complete reference solution. Only instructor-owned methods dispatch ROS motion."""

from microduck_workshop.agent.observation import translate_observation as translate_observation
from microduck_workshop.contracts import ContractError

# Observation reference source: src/microduck_workshop/agent/observation.py.
# A single production implementation prevents teacher/live safety-filter drift.


def step_forward(domain, args):
    """Validate the selector, return the instructor's real fixed-step receipt unchanged."""
    if not isinstance(args, dict) or (args and args != {"action": "step_forward"}):
        raise ContractError('only {} or {"action":"step_forward"} is permitted')
    # The instructor constructs .10/0/0/2.0, refreshes perception, dispatches the
    # separate ROS step service once and queries the independent physical verdict.
    return domain.step_forward(args)
