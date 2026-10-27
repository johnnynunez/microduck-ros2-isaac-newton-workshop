# Student capstone

Work in `tools.py`; do not edit the ROS gateway, simulator watchdog or motion envelope.

1. Implement `translate_observation`: expected episode/frame; strict numeric and tag-ID
   validation; capture age plus RPC latency; STOP overrides GO; a newly constructed allowlist.
2. Implement `walk_bounded`: exact four motion fields; use the shared
   `microduck_workshop.contracts.MotionCommand` validator; no clipping; call the
   instructor-owned `domain.walk_bounded` and return its actual receipt.

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
