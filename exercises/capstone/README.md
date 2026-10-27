# Student capstone

Work in `tools.py`; do not edit the ROS gateway, simulator watchdog or motion envelope.

1. Implement `translate_observation`: expected episode/frame; strict numeric and tag-ID
   validation; capture age plus RPC latency; STOP overrides GO; a newly constructed allowlist.
2. Implement `step_forward`: accept only `{}` or `{"action":"step_forward"}`;
   reject numeric choices and unknown keys. Call instructor-owned `domain.step_forward`
   and return its actual receipt. It constructs the fixed `.10/0/0/2.0` request for
   `step-forward-v1`, rechecks perception, and uses the distinct ROS step service.
   A verified legacy standstill/turn is not completion of the forward-step objective.

From the repository root, in the agent environment:

```bash
python scripts/agent_check_exercise.py
```

This intentionally fails until you implement both TODOs. The checks use explicitly fake
CPU transports; passing them is not a robot demonstration. Compare the explicit reference
only when ready:

```bash
python scripts/agent_check_exercise.py --tools-file solutions/capstone/tools.py
```

Follow [the full capstone guide](../../docs/capstone.md) for the real ROS launch and
`python -m microduck_workshop.agent.run --tools-file exercises/capstone/tools.py ...`.
The default live runner never substitutes the solution for an incomplete student file.
