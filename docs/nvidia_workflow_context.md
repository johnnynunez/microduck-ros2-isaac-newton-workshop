# NVIDIA's MicroDuck workflow and this workshop

## Why this reference belongs in the introduction

The NVIDIA Technical Blog article **Using AI Agents to Teach Robots Like Microduck to Walk in Simulation** (23 October 2026, co-authored by Johnny Núñez) connects AI-assisted planning, asset creation, Isaac Sim environment assembly, Isaac Lab learning with Newton, policy evaluation, and preparation for physical deployment.[1]

Use it as context for the instructor's existing slides, not as evidence that this repository has passed its own live acceptance gates.

## Keep three roles separate

1. **Engineering agents prepare the experiment.** The article uses Hermes/Nemotron and Astra to help plan the course, create assets, assemble the environment, and organize training and validation.[1] In the workshop, preparation happens before class; students do not spend their two hours generating a complete obstacle course.
2. **The RL policy learns and executes motor behavior.** The article distinguishes parameter updates during training from evaluating a selected policy without that learning loop.[1] [Lab 3](labs/03-reinforcement-learning.md) makes this distinction concrete: inspect observations/actions/rewards, run a short actual update, then restore the separately evaluated inference candidate.
3. **The runtime agent chooses a bounded task action.** This workshop adds the [CASCADE capstone](labs/05-cascade.md): a local Qwen model observes an Isaac ROS result, requests one fixed step through ROS, and checks an independent physical verdict. The policy and Newton simulation execute the movement; the model does not generate joint targets token by token. This runtime tool-orchestration exercise is our workshop addition, not a capability established by the blog article.

```text
Before class: engineering agents → assets, environment, experiment configuration
Lab 3:       observations → policy actions → Newton rollout → PPO update
Lab 5:       onboard camera → Isaac ROS → local CASCADE agent → bounded ROS tool
                                                        ↓
                                      learned policy + Newton → verifier → agent
```

## Scale and evidence must not be confused

- **Article experiment:** adaptation of a pretrained locomotion policy for ramps and obstacles, with head-camera depth and robot-state observations; the article reports **4,096 parallel environments on an RTX PRO 6000 Blackwell Workstation Edition GPU**.[1]
- **Our short teaching experiment:** the recorded run made 512 native physics steps, four updates and 16 optimizer steps. Its [receipt](../verification/fresh-ppo.json) says `converged_gait=false` and `resumed_onnx=false`. It demonstrates optimizer work, not the article's ramp policy or convergence.
- **Our runtime exercise:** a camera-based GO/STOP signal game with a separately admitted fixed-step skill. It is not full obstacle-course navigation, a depth-navigation policy, or a hardware deployment.
- **Our hardware evidence:** local RTX PRO execution. A local result does not establish Brev instance readiness, L40S compatibility in practice, RTX Spark performance, or physical-robot safety. Consult [current readiness](../verification/READINESS.md) rather than inheriting a PASS from the article.

## What to emphasize about Newton and BAM

The article describes BAM as modeling servo effects including delays, mechanical backlash and shared-battery voltage effects, and discusses domain randomization and remaining sim-to-real differences.[1] Use that to explain why an ONNX input/output shape is not a complete robot contract. In this repository, inspect the exact [policy contract](../provenance/policy_contract.json), native actuator configuration, sensor timing, and measured outcomes; do not assume every effect mentioned in the article has been exercised by our short run.

Physical deployment is outside the article's detailed scope and outside this workshop's execution scope.[1] Do not send workshop commands to a real robot.

## Reading links versus executable pins

The article links to an Isaac Lab MicroDuck example, native-BAM walking demo, and a sim-to-real tutorial.[1] Treat its moving `develop` and early-access documentation links as further reading. Keep this workshop's [pinned source manifest](../provenance/sources.json) and GA runtime checks for installation; do not replace them with a moving branch or copy the article's RTX Spark Windows setup onto the Linux Brev instance.

No article figures, robot assets, or checkpoints are copied into this repository by this reference note. Their original terms remain separate from the workshop code license.

## Sources

[1] https://developer.nvidia.com/blog/using-ai-agents-to-teach-robots-like-microduck-to-walk-in-simulation — Using AI Agents to Teach Robots Like Microduck to Walk in Simulation
