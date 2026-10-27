import xml.etree.ElementTree as ET


def test_prepare_mjcf_preserves_paired_hinges_and_replaces_xml_pd(tmp_path):
    from microduck_workshop.sim.prepare import prepare_training_mjcf

    source = tmp_path / "source.xml"
    source.write_text(
        """<mujoco><compiler meshdir="assets"/><default><default class="chosen_actuator"><joint damping=".053" armature=".0018"/></default></default><worldbody><body name="link"><joint name="left_hip_yaw" class="chosen_actuator"/><joint name="passive_left_hip_yaw_backlash" class="backlash"/><geom name="left_foot_collision" type="box" size="1 1 1"/></body></worldbody><actuator><position joint="left_hip_yaw" kp=".55"/></actuator></mujoco>"""
    )
    output = prepare_training_mjcf(source, tmp_path / "derived")
    root = ET.parse(output).getroot()
    assert [x.get("name") for x in root.findall(".//worldbody/body/joint")] == [
        "left_hip_yaw",
        "passive_left_hip_yaw_backlash",
    ]
    assert root.find("actuator") is None
    assert root.find(".//geom").get("condim") == "3"
    assert (
        root.find(".//default[@class='chosen_actuator']/joint").get("solreffriction")
        == "-50000 -200"
    )


def test_native_rejects_unpinned_source_before_launch(tmp_path):
    import pytest

    from microduck_workshop.sim.native import MicroDuckRuntime

    source = tmp_path / "robot_allcollisions_backlash.xml"
    source.write_text("<mujoco/>")
    with pytest.raises(ValueError, match="asset SHA-256 mismatch"):
        MicroDuckRuntime(source, output_dir=tmp_path / "out")
