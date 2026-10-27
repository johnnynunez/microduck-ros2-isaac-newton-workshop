# Before class — arrive ready to observe, not to install

**Before 15:00. Setup/download/build time is outside the 120-minute lesson.**

## What you need

- A browser, SSH-capable terminal or VS Code remote connection, and the instructor's Brev access/credit instructions. One student uses one **L40S or RTX PRO** GPU instance. No laptop GPU is required.
- The public workshop repository at the instructor's tested revision; record that revision rather than updating during class.
- Ubuntu **24.04 Noble**, Python **3.12**, Isaac Sim **6.2.0.0** distribution / **6.2** product, Isaac Lab **3.0**, **Newton**, Isaac ROS **5.0**, and ROS 2 **Lyrical** packages from **NVIDIA's buildfarm**. Ordinary Ubuntu ROS installation instructions may lead to a different stack; do not substitute Jazzy.
- The prepared ROS workspace, custom workshop interfaces, sensor/perception packages, Python test tools and a warmed local CASCADE model. Large container, robot, model and shader downloads must finish before class.

The [repository README](../../README.md) is the launch/setup authority. Follow its tested Brev procedure and inspect its readiness/evidence limits. If a complete procedure is not published for your revision, ask the instructor; do not start an improvised installation while the lesson runs.

## 1. Know what you are downloading

Read [NOTICE](../../NOTICE), [the public source manifest](../../provenance/sources.json) and [the policy contract](../../provenance/policy_contract.json).

- Pollen software and MJCF: **Apache-2.0**.
- Pollen STL meshes and converted derivatives: **CC BY-NC-SA 4.0**. Fetch separately through the approved downloader, review the NonCommercial/ShareAlike terms, and explicitly acknowledge them. A public repository is not permission for every commercial use. Preserve attribution.
- Public VelStand v8 ONNX: an inference **candidate**, not a verified Newton gait or a full PPO resume checkpoint. Keep its pinned revision/hash.
- MJLab is Pollen's upstream training reference, **not** our Isaac Lab/Newton runtime. Private Creative/NVIDIA assets and private teacher checkpoints are not prerequisites.

Do not waive a checksum/license failure just to reach the preview. Ask staff.

## 2. Prepare the terminals

Keep these roles separate:

| Terminal | Purpose | Rule |
|---|---|---|
| Simulation/runtime | Warm, already running Newton telemetry before Lab 1 | Use the prepared simulator environment, not a random ROS shell |
| ROS tools | `ros2`, the gateway workspace and observer | Lyrical underlay plus built workshop overlay, same instance/domain |
| Tests/editor | Edit the two helper TODOs and run CPU pytest | Python 3.12; GPU and ROS are not needed for helper tests |

Keep the launch terminal alive, and open a second ROS tools terminal for inspection. Copy the exact environment/sourcing procedure from the tested setup instructions. Do not source Jazzy and then Lyrical in the same shell. Use local-host discovery with the configured `ROS_DOMAIN_ID`; domain IDs separate graphs but are **not authentication**.

Read-only checks in the prepared terminals:

```bash
# Any repository terminal
git rev-parse HEAD
python --version

# Prepared ROS terminal
printenv ROS_DISTRO
ros2 pkg prefix microduck_workshop_interfaces
ros2 interface show microduck_workshop_interfaces/srv/Observe
ros2 topic list -t
```

Expect the configured distro to be `lyrical` and the custom interface to resolve. Seeing a package name does not prove its node is running. An empty graph is a setup issue to fix before class, not a reason to publish fabricated telemetry.

## 3. Warm and check the real path

Ask the instructor to confirm the release's recorded startup path on your instance:

- Real Newton playback, actual encoder/IMU data and `/clock` are already running at zero motion intent for the ROS lesson; the simulation lab will inspect ownership rather than launch a duplicate owner.
- Actual onboard RGB and matching calibration are available. The authenticated/secure Brev preview is reachable. Human overview and onboard camera are distinguishable.
- Isaac ROS perception and local-model weights are installed/warmed even if the agent remains disabled until the capstone.
- Emergency stop, wall watchdog and operator-only re-arm have been rehearsed. No physical MicroDuck is connected.

**Network boundary:** keep the command transport on loopback. Use Brev secure preview or an authenticated tunnel for viewing. Do not expose unauthenticated motion services, the local model API or DDS to the public Internet; a classroom `ROS_DOMAIN_ID` is not a security control.

## 4. Put shutdown on your calendar now

Record when your one-day credits expire and set your own reminder **before the 24-hour expiry**. Do not assume credits or stopping a container stop charges. At the end you must stop/delete the **Brev cloud instance**, verify its cloud state, and check any retained storage charges. Follow the [shutdown checklist](06-wrap-up.md).

## Checkpoint

Before 15:00, show staff: your pinned revision, a real topic list including joint states and `/clock`, a reachable private preview, and the place in Brev where you will stop/delete the instance. Mark any missing runtime gate explicitly; do not write “ready” based only on CPU tests.

Next: [student route](README.md) and [ROS basics](01-ros-basics.md).
