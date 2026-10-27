import importlib


def test_play_cli_has_bounded_public_asset_entrypoint():
    play = importlib.import_module("microduck_workshop.sim.play")
    args = play.parser().parse_args(
        ["--asset-root", ".cache/assets", "--mode", "validate", "--steps", "350"]
    )
    assert args.steps == 350
    assert args.mode == "validate"
    assert args.policy_mode == "training"


def test_operator_can_select_stop_signal_at_launch():
    from microduck_workshop.sim.play import parser

    args = parser().parse_args(["--asset-root", ".cache/assets", "--tag-id", "1", "--cameras"])
    assert args.tag_id == 1 and args.cameras


def test_evaluator_does_not_confuse_ack_with_motion():
    from microduck_workshop.sim.evaluate import evaluate_trace

    trace = [
        {
            "sim_time": t,
            "command": [0.08, 0, 0],
            "phase": "walk",
            "root_pose": [0, 0, 0.12, 0, 0, 0, 1],
            "root_velocity": [0] * 6,
        }
        for t in [0, 0.5, 1, 1.5, 2]
    ]
    verdict = evaluate_trace(trace)
    assert not verdict["walk_stop_resume_verified"]
    assert verdict["segments"]["walk"]["forward_displacement_m"] == 0


def test_motion_evaluator_rejects_stationary_ack_and_interrupted_motion():
    from microduck_workshop.contracts import MotionCommand
    from microduck_workshop.sim.evaluate import evaluate_motion

    cmd = MotionCommand("ep", "r", 0, 0.08, 0, 0, 1)
    trace = [
        {"sim_time": t, "root_pose": [0, 0, 0.12, 0, 0, 0, 1], "root_velocity": [0] * 6}
        for t in [0, 0.5, 1, 1.5]
    ]
    assert not evaluate_motion(trace, cmd, "completed")["verified"]
    trace[-1]["root_pose"][0] = 0.08
    assert evaluate_motion(trace, cmd, "completed")["verified"]
    assert not evaluate_motion(trace, cmd, "stopped")["verified"]
