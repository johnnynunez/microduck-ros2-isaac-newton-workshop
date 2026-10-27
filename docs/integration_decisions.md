# Final scene and timing decisions

The [measured camera-payload experiment](camera_latency.md) retains its original outcomes: reducing the authored head render product to 320×240 fixed the observed large-image delivery loss, but did not make the moving-camera game succeed.

## A fixed board that fits the onboard view

The original teaching board was centered at `(0.65, 0.0, 0.23)` metres. A retained real image near an empty detection cuts the marker's top edge. It is nearby evidence with a different sequence, not the detector's exact input.

Before the next trial, the lesson's **static** board center was set to `(1.0, 0.0, 0.16)` metres. Both GO and STOP use identical geometry. The outer board remains 0.25 m and its black-border marker 0.20 m. Camera optics, pose on the robot, render intrinsics and marker textures are unchanged. `camera_authorship.json` records the actual authored vertices. There is no runtime look-at controller, moving target, visibility override, invented detection or ground-truth input to the actor/agent.

The next real trial showed the full board inside the image but still expired during execution. That failure is preserved; improved composition alone is not a successful maneuver.

## Read-only wait versus motion and safety deadlines

The tool's default **read-only wait for the independent verdict** now uses its already-supported maximum of **8 wall-clock seconds**, rather than 5. Physics/rendering is slower than wall time on the measured local configuration. A longer observer wait does not create a successful verdict and does not keep a command alive.

Unchanged:

- Motion horizon: **2 simulation seconds**, comprising 1 second of learned drive and 1 second of learned zero/balance.
- Evaluator: original completion + 0.35 simulation-second collection and all original displacement, upright, yaw and rest bounds.
- Original-capture freshness: **0.5 wall-clock seconds**.
- Actuator lease: **0.5 wall-clock seconds**, independently renewed.
- No automatic motion retry, no stop reset, no unverified success.

The observer's hard maximum remains 8 seconds. Earlier 5-second trials keep their original outcomes. This decision was recorded before the next run, not selected after obtaining a passing motion verdict.

## Native-only reconfirmation

A separate fresh run of an immutable merged-source snapshot passed step and resume with unchanged physical criteria, rejected new commands during both verifier tails, and cancelled malformed authenticated renewal. [The new receipt](../provenance/native_merged_validation.json) binds its sources and five raw artifact hashes. Cameras were **off** in that confirmation; it does not promote the still-pending camera/ROS/model game.
