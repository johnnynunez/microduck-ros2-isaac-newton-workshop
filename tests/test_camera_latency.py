"""Camera budget regressions; native RTX/ROS measurements live in camera_latency.md."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from microduck_workshop.sim import camera


@pytest.mark.parametrize("resolution", [(320, 240), (640, 480)])
def test_lower_payload_camera_keeps_optics_and_truthful_dimensions(
    monkeypatch, tmp_path, resolution
):
    # SDK construction is unavailable on the lightweight test host. Exercise the
    # actual scene-authoring function with configuration-only SDK stand-ins.
    class CameraCfg(SimpleNamespace):
        OffsetCfg = SimpleNamespace

    modules = {
        "isaaclab": SimpleNamespace(),
        "isaaclab.sim": SimpleNamespace(
            PinholeCameraCfg=SimpleNamespace,
            DomeLightCfg=SimpleNamespace,
            SpawnerCfg=type("SpawnerCfg", (), {}),
        ),
        "isaaclab.assets": SimpleNamespace(AssetBaseCfg=SimpleNamespace),
        "isaaclab.sensors": SimpleNamespace(CameraCfg=CameraCfg),
        "isaaclab.utils": SimpleNamespace(configclass=lambda cls: cls),
        "isaaclab_physx": SimpleNamespace(),
        "isaaclab_physx.renderers": SimpleNamespace(IsaacRtxRendererCfg=SimpleNamespace),
        "scipy": SimpleNamespace(),
        "scipy.spatial": SimpleNamespace(),
        "scipy.spatial.transform": SimpleNamespace(
            Rotation=SimpleNamespace(
                from_matrix=lambda _: SimpleNamespace(as_quat=lambda: [0, 0, 0, 1])
            )
        ),
    }
    modules["isaaclab"].sim = modules["isaaclab.sim"]
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(camera, "head_mount_from_source", lambda _: ((0, 0, 0), (0, 0, 0, 1)))
    monkeypatch.setattr(camera, "make_tag_texture", lambda _, path: Path(path))
    scene = SimpleNamespace()
    receipt = camera.configure_cameras(scene, "unused.xml", tmp_path, head_resolution=resolution)
    assert (scene.head_camera.width, scene.head_camera.height) == resolution
    assert (receipt["width"], receipt["height"]) == resolution
    assert scene.head_camera.data_types == ["rgb"]
    assert scene.head_camera.spawn.focal_length == 18.0
    assert scene.head_camera.spawn.horizontal_aperture == 24.0
    assert scene.head_camera.spawn.vertical_aperture == 18.0
    assert (scene.overview_camera.width, scene.overview_camera.height) == (640, 480)


def test_play_defaults_to_lower_payload_and_keeps_full_resolution_opt_in():
    from microduck_workshop.sim.play import parser

    args = parser().parse_args(["--asset-root", "assets", "--cameras"])
    assert args.head_camera_resolution == "320x240"
    args = parser().parse_args(
        ["--asset-root", "assets", "--cameras", "--head-camera-resolution", "640x480"]
    )
    assert args.head_camera_resolution == "640x480"
