"""Opt-in live GPU gate. Never replaces Newton with a fixture."""

import os

import numpy as np
import pytest

pytestmark = pytest.mark.gpu


def test_public_microduck_newton_reset_step_and_sensor_shapes(tmp_path):
    mjcf = os.environ.get("MICRODUCK_MJCF")
    if not mjcf:
        pytest.skip("MICRODUCK_MJCF required; run through the pinned Isaac Lab environment")
    from microduck_workshop.sim.native import MicroDuckRuntime

    with MicroDuckRuntime(mjcf, output_dir=tmp_path, cameras=False) as runtime:
        assert runtime.identity["newton"] == "1.6.1"
        assert runtime.identity["isaaclab_git_sha"] == "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"
        assert runtime.identity["physics_owner"] == "isaaclab_newton.physics.NewtonManager"
        assert len(runtime.joint_names) == 28  # 14 servo + 14 coaxial backlash
        for _ in range(8):
            sample = runtime.step_zero_effort()
        assert len(sample["joint_position"]) == 14
        assert len(sample["joint_velocity"]) == 14
        assert len(sample["imu"]["angular_velocity"]) == 3
        assert np.isfinite(sample["joint_position"]).all()
        assert sample["sim_time"] > 0
        import json

        receipt = {
            "evidence_kind": "LIVE_NEWTON_RESET_STEP",
            "physics_steps": 8,
            "identity": runtime.identity,
            "last_native_sample": sample,
        }
        (tmp_path / "reset_step_receipt.json").write_text(json.dumps(receipt, indent=2))
        print("NATIVE_RESET_STEP_ASSERTIONS_PASSED", json.dumps(receipt), flush=True)
        runtime.enable_bam()
        from microduck_workshop.policy.contract import HOME

        for _ in range(8):
            sample = runtime.step_target(HOME)
        assert runtime.bam_receipt["friction_native_verified"]
        assert np.isfinite(sample["joint_velocity"]).all()
        (tmp_path / "bam_receipt.json").write_text(json.dumps(runtime.bam_receipt, indent=2))
        print("NATIVE_BAM_ASSERTIONS_PASSED", json.dumps(runtime.bam_receipt), flush=True)


def test_actual_head_camera_pixels_and_apriltag_input(tmp_path):
    mjcf = os.environ.get("MICRODUCK_MJCF")
    if not mjcf or os.environ.get("MICRODUCK_CAMERA") != "1":
        pytest.skip("opt-in live RTX camera test requires MICRODUCK_CAMERA=1 and MICRODUCK_MJCF")
    from microduck_workshop.policy.contract import HOME
    from microduck_workshop.sim.http import SnapshotStore
    from microduck_workshop.sim.intent import IntentOwner
    from microduck_workshop.sim.native import MicroDuckRuntime

    tag_id = int(os.environ.get("MICRODUCK_TAG_ID", "0"))
    with MicroDuckRuntime(mjcf, output_dir=tmp_path, cameras=True, tag_id=tag_id) as runtime:
        runtime.enable_bam()
        store = SnapshotStore(IntentOwner("camera_test"), runtime=runtime.identity)
        for _ in range(40):
            runtime.step_target(HOME)
        runtime.publish_camera(store, "camera_test")
        assert store.camera is not None
        assert store.camera_info["width"] == 640
        (tmp_path / "head_camera.jpg").write_bytes(store.camera.jpeg)
        import cv2

        image = cv2.imdecode(np.frombuffer(store.camera.jpeg, np.uint8), cv2.IMREAD_COLOR)
        assert image.shape == (480, 640, 3) and image.std() > 10
        detector = cv2.aruco.ArucoDetector(
            cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
        )
        _, ids, _ = detector.detectMarkers(image)
        assert ids is not None and tag_id in ids.flatten(), (
            "Real onboard pixels must contain the authored signal"
        )
        import json

        receipt = {
            "evidence_kind": "LIVE_RTX_PIXELS_CPU_DETECTOR_INPUT_CHECK_NOT_ISAAC_ROS",
            "detected_ids": ids.flatten().tolist(),
            "calibration": store.camera_info,
            "sequence": store.camera.sequence,
            "sim_time": store.camera.sim_time,
        }
        (tmp_path / "camera_receipt.json").write_text(json.dumps(receipt, indent=2))
        print("NATIVE_CAMERA_ASSERTIONS_PASSED", json.dumps(receipt), flush=True)
