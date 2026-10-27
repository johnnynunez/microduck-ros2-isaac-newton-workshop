"""Public Isaac Lab 3.0 / Newton owner; imports intentionally lazy.

No Sim-native physics engine is created. The initial root/joint writes below are
an episode reset only; subsequent execution changes actuator efforts exclusively.
"""

import hashlib
import json
import subprocess
import sys
import time
import traceback
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path

import numpy as np

from microduck_workshop.policy.contract import HOME, JOINT_NAMES, PHYSICS_DT


class MicroDuckRuntime:
    def __init__(
        self,
        mjcf,
        *,
        output_dir,
        cameras=False,
        device="cuda:0",
        tag_id=0,
        head_camera_resolution=(640, 480),
    ):
        self.mjcf = Path(mjcf).resolve()
        self.asset_sha256 = hashlib.sha256(self.mjcf.read_bytes()).hexdigest()
        if self.asset_sha256 != "ccee92e435e39eefc64ee99745823751492ae7f948d835c89701710717e71de8":
            raise ValueError(f"asset SHA-256 mismatch: {self.asset_sha256}")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cameras = cameras
        self.head_camera_resolution = head_camera_resolution
        if tag_id not in (0, 1):
            raise ValueError("tag_id must be 0 GO or 1 STOP")
        self.tag_id = tag_id
        self.device = device
        self.stack = ExitStack()
        self.sim_time = 0.0
        self.sequence = 0
        self._camera_reported = set()

    def __enter__(self):
        import torch
        from isaaclab.app import launch_simulation
        from isaaclab.sim import SimulationCfg
        from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg

        self.torch = torch
        cfg = SimulationCfg(
            dt=PHYSICS_DT,
            device=self.device,
            render_interval=4,
            use_newton_actuators=False,
            physics=NewtonCfg(
                solver_cfg=MJWarpSolverCfg(
                    nconmax=200,
                    njmax=1500,
                    iterations=100,
                    ls_iterations=50,
                    integrator="implicitfast",
                )
            ),
            log_dir=str(self.output_dir / "lab_logs"),
        )
        self.stack.enter_context(
            launch_simulation(
                cfg,
                {
                    "headless": True,
                    "require_kit": True,
                    "enable_cameras": self.cameras,
                    "device": self.device,
                    "multi_gpu": False,
                },
            )
        )
        try:
            from isaaclab.sim import SimulationContext
            from isaaclab_newton.physics import NewtonManager

            self.sim = SimulationContext(cfg)
            self._build_scene()
            self.sim.reset()
            self.manager = NewtonManager
            self.joint_names = list(self.robot.joint_names)
            from .joint_map import map_merged_joints

            limits = self.robot.data.joint_pos_limits.torch[0].cpu().numpy()
            self.servo_ids, self.backlash_ids = map_merged_joints(self.joint_names, limits)
            self.identity = {
                name: version(name)
                for name in (
                    "isaaclab",
                    "isaacsim",
                    "newton",
                    "mujoco",
                    "mujoco-warp",
                    "warp-lang",
                    "torch",
                )
            }
            import isaaclab

            lab_checkout = Path(isaaclab.__file__).resolve().parents[3]
            lab_sha = subprocess.check_output(
                ["git", "-C", str(lab_checkout), "rev-parse", "HEAD"], text=True
            ).strip()
            if lab_sha != "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4":
                raise RuntimeError(f"Isaac Lab is not the public v3.0.0 source pin: {lab_sha}")
            self.identity.update(
                physics_owner="isaaclab_newton.physics.NewtonManager",
                device=torch.cuda.get_device_name(self.device),
                asset_sha256=self.asset_sha256,
                isaaclab_git_sha=lab_sha,
                model_body_count=NewtonManager.get_model().body_count,
                model_joint_count=NewtonManager.get_model().joint_count,
                joint_names=self.joint_names,
                camera_enabled=self.cameras,
                servo_ids=self.servo_ids,
                backlash_ids=self.backlash_ids,
                joint_limits=limits.tolist(),
            )
            if self.identity["newton"] != "1.6.1" or self.identity["isaacsim"] != "6.2.0.0":
                raise RuntimeError(f"runtime version mismatch: {self.identity}")
            (self.output_dir / "runtime_identity.json").write_text(
                json.dumps(self.identity, indent=2)
            )
            self._initial_reset()
            return self
        except BaseException:
            traceback.print_exc()
            self.stack.__exit__(*sys.exc_info())
            raise

    def _build_scene(self):
        import isaaclab.sim as sim_utils
        from isaaclab.actuators import IdealPDActuatorCfg
        from isaaclab.assets import ArticulationCfg, AssetBaseCfg
        from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
        from isaaclab.sensors import ImuCfg
        from isaaclab.sim.converters import MjcfConverter, MjcfConverterCfg
        from isaaclab.utils import configclass

        from .prepare import prepare_training_mjcf

        prepared = prepare_training_mjcf(self.mjcf, self.output_dir / "prepared")
        converter = MjcfConverter(
            MjcfConverterCfg(
                asset_path=str(prepared),
                usd_dir=str(self.output_dir / "converted"),
                force_usd_conversion=False,
                self_collision=True,
                fix_base=False,
                run_asset_transformer=True,
                run_multi_physics_conversion=True,
            )
        )
        self.usd_path = converter.usd_path
        robot_cfg = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(usd_path=self.usd_path, variants={"Physics": "mujoco"}),
            init_state=ArticulationCfg.InitialStateCfg(
                pos=(0, 0, 0.12), joint_pos={".*": 0.0}, joint_vel={".*": 0.0}
            ),
            # Zero-gain effort pass-through. BAM supplies all motor effort.
            actuators={
                "effort_sink": IdealPDActuatorCfg(
                    joint_names_expr=[".*"],
                    stiffness=0.0,
                    damping=0.0,
                    actuator_effort_limit=1.0675531184074794,
                    joint_effort_limit=1.0675531184074794,
                )
            },
        )

        @configclass
        class SceneCfg(InteractiveSceneCfg):
            robot = robot_cfg
            ground = AssetBaseCfg(prim_path="/World/Ground", spawn=sim_utils.GroundPlaneCfg())
            imu = ImuCfg(
                prim_path="{ENV_REGEX_NS}/Robot/Geometry/trunk_base", update_period=PHYSICS_DT
            )

        scene_cfg = SceneCfg(num_envs=1, env_spacing=2.0)
        if self.cameras:
            from .camera import configure_cameras

            self.camera_authorship = configure_cameras(
                scene_cfg,
                self.mjcf,
                self.output_dir / "textures",
                tag_id=self.tag_id,
                head_resolution=self.head_camera_resolution,
            )
            (self.output_dir / "camera_authorship.json").write_text(
                json.dumps(self.camera_authorship, indent=2)
            )
        self.scene = InteractiveScene(scene_cfg)
        self.robot = self.scene["robot"]
        self.imu = self.scene["imu"]
        if self.cameras:
            self.head_camera = self.scene["head_camera"]
            self.overview_camera = self.scene["overview_camera"]

    def _initial_reset(self):
        self.robot.write_root_pose_to_sim_index(
            root_pose=self.robot.data.default_root_pose.torch.clone()
        )
        self.robot.write_root_velocity_to_sim_index(
            root_velocity=self.robot.data.default_root_vel.torch.clone()
        )
        q = self.robot.data.default_joint_pos.torch.clone()
        q[:, self.servo_ids] = self.torch.as_tensor(HOME, device=self.device)
        self.robot.write_joint_position_to_sim_index(position=q)
        self.robot.write_joint_velocity_to_sim_index(
            velocity=self.robot.data.default_joint_vel.torch.clone()
        )
        self.robot.reset()
        self.imu.reset()
        self.sim.forward()
        if self.cameras:
            for _ in range(12):
                self.sim.render()
                self.head_camera.update(PHYSICS_DT, force_recompute=True)
                self.overview_camera.update(PHYSICS_DT, force_recompute=True)

    def enable_bam(self, **kwargs):
        """Bind BAM to the existing Lab solver; never instantiate another engine.

        GA exposes the owner model publicly but not generalized constraint forces;
        `_solver` is one explicitly version-pinned read-only integration seam.
        All actuator/friction writes still use the public indexed Lab APIs.
        """
        from .bam import BamM6

        self.bam = BamM6(**kwargs)
        self.solver = self.manager._solver
        model = self.manager.get_model()
        labels = model.mujoco.joint_dof_label
        native_servo = []
        for name in JOINT_NAMES:
            matches = [i for i, label in enumerate(labels) if label.rsplit("/", 1)[-1] == name]
            if len(matches) != 1:
                raise RuntimeError(f"Cannot resolve exact authored DOF {name}: {labels}")
            native_servo.append(matches[0])
        mapping = self.solver.mjc_dof_to_newton_dof.numpy()[0].tolist()
        self.mjc_servo = [mapping.index(i) for i in native_servo]
        # Read back native parameters, not merely successful property writes.
        params = self.solver.mjw_model
        armature = params.dof_armature.numpy()[0, self.mjc_servo]
        damping = params.dof_damping.numpy()[0, self.mjc_servo]
        solref = params.dof_solref.numpy()[0, self.mjc_servo]
        if not np.allclose(armature, self.bam.ARMATURE) or not np.allclose(
            damping, self.bam.FRICTION_VISCOUS
        ):
            raise RuntimeError(
                f"BAM motor physics mismatch: armature={armature}, damping={damping}"
            )
        if not np.allclose(solref, [-50000.0, -200.0]):
            raise RuntimeError(f"BAM native friction constraint mismatch: {solref}")
        self.bam_receipt = {
            "current_limit_A": self.bam.current_limit,
            "voltage": self.bam.voltage,
            "sag_gain": self.bam.sag_gain,
            "delay_physics_steps": self.bam.delay_steps,
            "motor_armature": armature.tolist(),
            "motor_damping": damping.tolist(),
            "friction_solref": solref.tolist(),
            "friction_native_verified": False,
            "native_servo_dofs": native_servo,
            "mjc_servo_dofs": self.mjc_servo,
        }

    def step_target(self, target):
        data = self.solver.mjw_data
        # Source BAM subtracts its own dry-friction rows from previous constraint
        # force before computing the external gearbox load.
        n = int(data.nefc.numpy()[0])
        kinds = data.efc.type.numpy()[0, :n]
        ids = data.efc.id.numpy()[0, :n]
        forces = data.efc.force.numpy()[0, :n]
        friction_force = np.zeros(self.solver.mj_model.nv, dtype=np.float32)
        mask = kinds == 1  # mujoco.mjtConstraint.mjCNSTR_FRICTION_DOF
        np.add.at(friction_force, ids[mask], forces[mask])
        ext = (-data.qfrc_bias.numpy()[0] + data.qfrc_constraint.numpy()[0] - friction_force)[
            self.mjc_servo
        ]
        q = self.robot.data.joint_pos.torch[0].cpu().numpy()
        dq = self.robot.data.joint_vel.torch[0].cpu().numpy()
        previous = self.robot.actuators.applied_effort.torch[0, self.servo_ids].cpu().numpy()
        motor, budget = self.bam.compute(
            target=target,
            encoder_position=q[self.servo_ids] + q[self.backlash_ids],
            motor_velocity=dq[self.servo_ids],
            external_torque=ext,
            previous_actuator_torque=previous,
        )
        self.robot.write_joint_friction_coefficient_to_sim_index(
            joint_friction_coeff=self.torch.as_tensor(budget[None], device=self.device),
            joint_ids=self.servo_ids,
        )
        sample = self.step_effort(motor)
        actual = self.solver.mjw_model.dof_frictionloss.numpy()[0, self.mjc_servo]
        if not np.allclose(actual, budget, atol=1e-6):
            raise RuntimeError("BAM friction budget did not reach native solver")
        self.bam_receipt.update(
            friction_native_verified=True,
            last_motor_torque=motor.tolist(),
            last_friction_budget=budget.tolist(),
        )
        return sample

    def evaluator_truth(self):
        """Isolated evaluator-only GT; never pass this to policy or HTTP snapshots."""
        return {
            "root_pose": self.robot.data.root_link_pose_w.torch[0].cpu().tolist(),
            "root_velocity": self.robot.data.root_link_vel_w.torch[0].cpu().tolist(),
        }

    def step_zero_effort(self):
        return self.step_effort(np.zeros(14, dtype=np.float32))

    def step_effort(self, effort):
        effort = np.asarray(effort, dtype=np.float32)
        if effort.shape != (14,) or not np.isfinite(effort).all():
            raise ValueError("effort must be finite shape (14,)")
        tensor = self.torch.as_tensor(effort[None], device=self.device)
        self.robot.actuators.target_command.set_effort_index(value=tensor, joint_ids=self.servo_ids)
        self.robot.write_data_to_sim()
        self.sim.step(render=False)
        self.sim_time += PHYSICS_DT
        self.sequence += 1
        self.robot.update(PHYSICS_DT)
        self.imu.update(PHYSICS_DT)
        return self.sample()

    def sample(self):
        q = self.robot.data.joint_pos.torch[0].detach().cpu().numpy()
        dq = self.robot.data.joint_vel.torch[0].detach().cpu().numpy()
        sample = {
            "sequence": self.sequence,
            "sim_time": self.sim_time,
            "capture_monotonic_s": time.monotonic(),
            "joint_names": list(JOINT_NAMES),
            "joint_position": (q[self.servo_ids] + q[self.backlash_ids]).tolist(),
            "joint_velocity": (dq[self.servo_ids] + dq[self.backlash_ids]).tolist(),
            "imu": {
                "angular_velocity": self.imu.data.ang_vel_b.torch[0].cpu().tolist(),
                "linear_acceleration": self.imu.data.lin_acc_b.torch[0].cpu().tolist(),
            },
        }
        if not np.isfinite(q).all() or not np.isfinite(dq).all():
            raise RuntimeError("nonfinite native state")
        return sample

    def publish_camera(self, store, episode_id):
        """Capture current native scene once; pixels and headers form one snapshot."""
        import io

        from PIL import Image

        from .http import Frame

        if not self.cameras:
            raise RuntimeError("camera rendering was not enabled")
        self.sim.render()
        captured = time.monotonic()
        for camera, overview in ((self.head_camera, False), (self.overview_camera, True)):
            camera.update(PHYSICS_DT * 4, force_recompute=True)
            rgb = camera.data.output["rgb"].torch[0].detach().cpu().numpy()[..., :3]
            if overview not in self._camera_reported:
                print(
                    "CAMERA_RAW",
                    {
                        "overview": overview,
                        "dtype": str(rgb.dtype),
                        "min": float(rgb.min()),
                        "max": float(rgb.max()),
                        "std": float(rgb.std()),
                    },
                    flush=True,
                )
                self._camera_reported.add(overview)
            if rgb.dtype != np.uint8:
                raise RuntimeError(
                    f"Expected RGB8 renderer output, got {rgb.dtype}; do not silently rescale"
                )
            rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
            buffer = io.BytesIO()
            Image.fromarray(rgb).save(buffer, format="JPEG", quality=95)
            k = camera.data.intrinsic_matrices.torch[0].cpu().numpy()
            calibration = {
                "width": rgb.shape[1],
                "height": rgb.shape[0],
                "frame_id": "microduck_overview_optical" if overview else "microduck_head_optical",
                "encoding": "rgb8",
                "distortion_model": "plumb_bob",
                "k": k.reshape(-1).tolist(),
                "d": [0.0] * 5,
                "r": np.eye(3).reshape(-1).tolist(),
                "p": [
                    float(k[0, 0]),
                    0.0,
                    float(k[0, 2]),
                    0.0,
                    0.0,
                    float(k[1, 1]),
                    float(k[1, 2]),
                    0.0,
                    0.0,
                    0.0,
                    1.0,
                    0.0,
                ],
            }
            store.publish_camera(
                Frame(buffer.getvalue(), episode_id, self.sequence, self.sim_time, captured),
                calibration,
                overview=overview,
            )

    def __exit__(self, *exc):
        if hasattr(self, "sim"):
            self.sim.stop()
            self.sim.clear_instance()
        return self.stack.__exit__(*exc)
