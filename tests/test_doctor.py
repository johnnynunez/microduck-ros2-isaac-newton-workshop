from microduck_workshop.doctor import evaluate_version_pins

GA = "e3f7d9ff1f5d7f8280de3ece9000b7117f66bcf4"


def test_dev_package_number_is_not_an_isaaclab_release():
    report = evaluate_version_pins(
        {
            "isaacsim": "6.2.0.0",
            "isaac_ros_apriltag": "5.0.0",
            "isaaclab": "37.2.0",
            "newton": "1.6.1",
        },
        None,
        False,
        "lyrical",
    )
    assert report["isaac_lab_ga_source"] is False
    assert report["version_pins_match"] is False
    assert report["runtime_exercised"] is False


def test_matching_pins_still_do_not_claim_runtime_execution():
    report = evaluate_version_pins(
        {
            "isaacsim": "6.2.0.0",
            "isaac_ros_apriltag": "5.0.0",
            "isaaclab": "37.2.0",
            "newton": "1.6.1",
        },
        GA,
        True,
        "lyrical",
    )
    assert report["version_pins_match"] is True
    assert report["runtime_exercised"] is False


def test_old_ros_and_wrong_import_origin_fail_preflight():
    report = evaluate_version_pins(
        {"isaacsim": "6.2.0.0", "isaac_ros_apriltag": "5.0.0", "newton": "1.6.1"}, GA, True, "jazzy"
    )
    assert report["ros_lyrical"] is False
    report = evaluate_version_pins(
        {"isaacsim": "6.2.0.0", "isaac_ros_apriltag": "5.0.0", "newton": "1.6.1"},
        GA,
        False,
        "lyrical",
    )
    assert report["version_pins_match"] is False


def test_rc_or_old_sim_is_not_silently_relabelled_ga():
    for version in ["6.1.0.0", "6.2.0-rc.14", None]:
        report = evaluate_version_pins(
            {"isaacsim": version, "newton": "1.6.1"}, GA, True, "lyrical"
        )
        assert report["isaac_sim_62_wheel"] is False
