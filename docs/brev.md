# NVIDIA Brev: one-day workshop environment

**No paid instance or Launchable has been created by this repository.** Local RTX PRO verification is not a Brev/L40S receipt. The instructor supplies one-day credits; availability, rates and credit coverage must be checked in the Brev Console before deployment.

## Instructor preparation (before the 120-minute session)

Use the current [Launchables builder](https://docs.nvidia.com/brev/concepts/launchables) and [custom-container guide](https://docs.nvidia.com/brev/guides/development-tools/custom-containers). Supported builder fields, not an invented JSON provisioning API:

| Builder section | Workshop choice |
| --- | --- |
| Details | MicroDuck ROSCon España 2026; state simulation-only, noncommercial asset terms, two-hour lesson and one-day credit window |
| Default hardware | One **L40S** or **RTX PRO** GPU; check actual VRAM and driver; choose >=200 GiB storage for Sim/Lab, ROS images, assets, models and caches (workshop recommendation, not vendor minimum) |
| Software | **VM Mode** with CUDA/Docker, using the setup script below; this makes repo-local build context and sibling runtimes explicit |
| Source | The instructor's **actual published repository URL** at the selected immutable commit. Do not substitute a guessed URL |
| Network | No public DDS, HTTP command, model-serving or simulator control ports. Ports are 8765 human preview, 8766 private simulator, 8080 private classroom model endpoint. Only a human preview HTTP service may receive a Brev-authenticated **Secure Link**, after it is configured by the simulation owner |
| Launch parameters | `WORKSHOP_GPU` default `0`; `ROS_DOMAIN_ID` default `27`; `WORKSHOP_ROS_IMAGE` exact tested image reference if instructor publishes it. No reusable secret defaults |
| View access | Instructor decides organization/link-only/public. Copy the real badge/link from the Console only after creation |

Alternative **Docker Compose** mode accepts an uploaded Compose file or a GitHub/GitLab URL. `compose.yaml` is real and validated, but builds require the complete repository context and prebuilt base. For a URL-only Launchable, publish the tested OCI image first and provide a Compose configuration referencing its digest with no local build dependency. Do not claim that merely pointing Brev at a relative `build: .` makes the whole repository available. VM Mode is the documented reference path here.

VM setup script, after Brev checks out the selected source repository:

```bash
# Run from the actual checkout root, not an assumed /workspace path.
bash scripts/brev_setup.sh
# Parent-owned asset fetch (requires merged parent asset module):
python -m microduck_workshop.assets fetch --accept-mesh-license --destination .cache/assets
```

The read-only preflight checks Docker/Compose, GPU inventory, driver >=595 and free disk. Isaac ROS 5 requires CUDA 13.2+ and Ubuntu 24.04 userspace. Noble Lyrical packages intentionally come from NVIDIA's buildfarm. Do **not** change host drivers without the instance owner's approval, and do not downgrade to Jazzy as a workaround. Select a compatible Brev environment instead.

Brev's launch parameters are launch-time inputs: later SSH shells and later Compose invocations do not automatically inherit them. Record nonsecret selections in a local `.env` if needed. Never print credentials or put them in images/commits; this local-model workshop does not need a hosted LLM API key.

## Student access and start

1. Instructor verifies the account, credits, one-day expiry and chosen instance **before** clicking Deploy. Deployment consumes paid resources; it is a manual authorized action.
2. Open Brev's SSH/VS Code connection workflow. Use a terminal in the selected checkout. Browser preview goes only through the authenticated Secure Link or an SSH forward; do not expose control ports to all IPs.
3. Confirm the real GPU and versions with `bash scripts/brev_preflight.sh`. Select `WORKSHOP_GPU=0` on a one-GPU instance.
4. Follow the simulation owner's startup instructions. Verify `/v1/health` on loopback reports the real Lab/Newton runtime, not a fixture.
5. Run `bash scripts/brev_start.sh`. The container limit is **24 GiB RAM, 8 CPU**, with explicit GPU reservation. This does not cap total VM usage by sibling simulation/model runtimes: check the combined budget before loading all models.
6. Run the DDS/AprilTag smoke and live sensor gate before calling the capstone ready. An official rosbag pass alone is not a live MicroDuck pass.

## Shutdown and billing checklist

- [ ] Stop the agent and issue `/workshop/microduck/emergency_stop`. ACK is not proof of physical rest; here there is no physical robot.
- [ ] `bash scripts/brev_stop.sh` stops this Compose stack and lease renewal. Stop the simulator/model jobs through their own documented launchers.
- [ ] Export your code and small test receipts. Respect the separate upstream asset licenses; do not republish caches/weights by accident.
- [ ] In the Brev Console **stop the instance** and verify the stopped state. Stopping containers, disconnecting SSH or closing the browser does **not** stop the VM.
- [ ] If the day's work is finished, delete the instance and unneeded persistent storage according to the Console's confirmation. Check provider/storage charges and credit balance; stopped compute may still incur storage charges.
- [ ] Instructor confirms no running workshop instances remain after the one-day credit window. Do not automate deletion of someone else's resources.

## Execution scope

Receipts must distinguish `local RTX PRO`, `Brev RTX PRO`, and `Brev L40S`. This repository's local smoke cannot establish cloud provisioning, credit allocation, browser Secure Link operation, or L40S performance. A cloud rehearsal is a separate, explicit instructor gate.
