# Wrap-up — keep the evidence, stop the bill

**5 minutes · 16:55–17:00.** Stop experiments now, even if a run is nearly finished.

## 1. Explain the system — 1 minute

Tell a neighbor which component performs each job: ROS messages/services, Newton dynamics, learned joint control, CUDA image detection, local-model tool selection, and independent verification. Name one thing your evidence did **not** establish.

## 2. Save only what you need — 1 minute

Save your helper edits, short training receipt and capstone trace. Record the repository revision, actual device/runtime, and whether each stage was run on your own Brev instance or merely observed. Keep failures. A local RTX PRO receipt is not an L40S or Brev receipt.

Do not commit credentials, lease tokens, raw private prompts or bundled third-party meshes/weights. Retain attribution and license notices with downloaded assets.

## 3. Stop processes, then the instance — 3 minutes

1. With the gateway still running, request the rehearsed emergency stop and inspect its status. Zero intent is not torque-off or a physical safety verdict. On an unknown result, notify staff and follow the supervisory shutdown procedure.
2. Stop the agent, training and workshop runtime using the exact teardown command in the [README](../../README.md). Confirm the processes/containers exited; closing a browser tab or SSH session is not enough.
3. Open **Brev's instance management** and deliberately **stop or delete the cloud instance**. Save needed work before deletion; deletion may destroy it. Verify the resulting cloud state, not just a closed terminal.
4. Check for retained disks/storage and any remaining charges in the account/provider view. Stopped compute can still leave billable storage. Resolve that with staff rather than assuming zero cost.
5. Keep your personal reminder for **before the one-day / 24-hour credit expiry** until the cloud state and retained resources are confirmed. Do not assume credits automatically shut instances down.

**Stopping a Docker container does not end Brev instance charges.** No code in this lesson provisions paid resources or operates a physical robot for you.

## Checkpoint

Show the instructor or a partner: saved work, stopped workshop processes, and the cloud instance's confirmed stopped/deleted state. Report unresolved resources before leaving. Do not publish billing/account screenshots containing private details.

## After the workshop

Try one controlled change at a time: another read-only ROS subscriber, a reward ablation across seeds, or an additional visual signal with explicit refusal tests. Keep Newton, source provenance and the bounded control path intact. Physical robot deployment requires a separate hardware/safety project and is **out of scope** here.

[Return to the course index](README.md) · [Official Pollen runtime](https://github.com/pollen-robotics/microduck) · [Upstream MJLab reference](https://github.com/pollen-robotics/microduck_rl) · [Public policy set](https://huggingface.co/pollen-robotics/microduck-policies) · [CASCADE](https://github.com/johnnynunez/cascade)
