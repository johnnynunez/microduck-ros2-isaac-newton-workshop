# Student-policy v3 evidence (R1–R4 repair)

These append-only **publication snapshots are not deployable bundles**. Native execution and raw artifact replay produced the results; CPU adversarial fixtures did not authorize them. Native-only validation does **not** establish ROS/perception/CASCADE acceptance.

`redactions.json` records the original and public SHA-256 for every snapshot and the exact JSON pointers redacted. Private absolute runtime paths are replaced with an explicit redaction marker, not invented portable execution paths. The original training/admission/HTTP receipts and all raw observations, actions, truth, checkpoints, and weights remain unchanged in private `train-v3`, `admit-v3`, `handoff-v3`, `handoff-v3-confirmation`, and `default-v3` bundles. The manifest binds the **original** training receipt hash, not its redacted publication copy.

The fresh run used the pinned public actor as an actor-only warm start, seed 7, four PPO updates, horizon 32, learning rate 1e-6, and initial action standard deviation .005. It is neither full PPO resume nor a convergence claim. Admission verifies the four fixed timing cases, full control-period chronology, actual selected ONNX outputs on every retained observation, previous RAW action/filter semantics, and unchanged native physical gates. The separate HTTP confirmations retain proof expiry, lease expiry, priority STOP, and non-rearm checks for both the student and canonical default.

Use the unchanged external CLI to regenerate a complete bundle:

```sh
python -m microduck_workshop.sim.train --asset-root ASSETS \
  --warm-start-onnx ASSETS/policies/velstand.onnx --output NEW_RUN \
  --seed 7 --updates 4 --horizon 32
python -m microduck_workshop.sim.admit_policy --asset-root ASSETS \
  --policy-manifest NEW_RUN/policy_manifest.json --output NEW_ADMISSION
python -m microduck_workshop.sim.play --asset-root ASSETS \
  --policy-manifest NEW_RUN/policy_manifest.json \
  --policy-admission NEW_ADMISSION/admission.json \
  --step-profile step-forward-v1 --mode serve --steps 0 --cameras
```

Mount the **whole** training directory (including `initial.pt` and `transitions.jsonl`) and whole admission directory read-only for deployment. The operator's identity-only reader remains lightweight; native selection and the admission supervisor additionally replay the exact ONNX. Control source changes require new native evidence. Identity/agent/ROS files are outside that fingerprint and need their own identity and joined ROS acceptance checks. Historical v1 receipts are retained as history, not relabeled to authorize v3 source.

## Preserved limitations and unsuccessful attempt

The first v3 native HTTP episode failed the resume straight-line yaw gate: -0.1652059804161195 rad exceeded the unchanged absolute 0.15 rad bound. `first_attempt_native_handoff.json` preserves its failed status and error. One subsequent fresh episode with the same actor, flags and unchanged limits passed both physical requests and all expiry/STOP checks; `native_handoff.json` is that confirmation. This is **not** a robustness or convergence claim. The failed HTTP trace contained 51 drive and 51 settle samples per request, while admission deliberately enforces exactly 50+50; joined HTTP/ROS scheduling remains a separate integration concern.

The earlier v2 successful native evidence is preserved in `../student_policy_v2/`, but is bound to the source before the additional supervisor-exception correction. It cannot authorize the final v3 source. Files prefixed `cpu_` record rerun adversarial rejection/audit probes, not new simulated physical episodes. Their actual different zero-output ONNX is rejected specifically for raw-output mismatch.
