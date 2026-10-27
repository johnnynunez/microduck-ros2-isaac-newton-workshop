"""Authored teaching pinhole camera and real textured tag36h11 signal boards."""

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from microduck_workshop.policy.contract import HOME, JOINT_NAMES


def head_mount_from_source(mjcf):
    """Static source-model FK at HOME, not runtime GT or a navigation signal.

    Reuse the source head_camera site, with 5 mm forward clearance from the lens
    mesh, looking along trunk +X at HOME. The real camera then follows that link.
    """
    from scipy.spatial.transform import Rotation

    home = dict(zip(JOINT_NAMES, HOME))

    def descend(body, rotation):
        quat = np.fromstring(body.get("quat", "1 0 0 0"), sep=" ")
        rotation = rotation * Rotation.from_quat(quat[[1, 2, 3, 0]])
        for joint in body.findall("joint"):
            axis = np.fromstring(joint.get("axis", "0 0 1"), sep=" ")
            rotation = rotation * Rotation.from_rotvec(axis * home.get(joint.get("name"), 0.0))
        if body.get("name") == "jaw_soft":
            return rotation
        for child in body.findall("body"):
            result = descend(child, rotation)
            if result is not None:
                return result
        return None

    xml = ET.parse(mjcf).getroot()
    root = xml.find("worldbody/body")
    rotation = descend(root, Rotation.identity())
    if rotation is None:
        raise ValueError("source model has no jaw_soft head body")
    site = xml.find(".//body[@name='jaw_soft']/site[@name='head_camera']")
    if site is None:
        raise ValueError("source model has no head_camera mount site")
    source_position = np.fromstring(site.get("pos"), sep=" ")
    position = source_position + rotation.inv().apply([0.005, 0, 0])
    return tuple(position), tuple(rotation.inv().as_quat())


def make_tag_texture(tag_id, output):
    import cv2

    if tag_id not in (0, 1):
        raise ValueError("teaching signals are tag0 GO and tag1 STOP")
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    marker = cv2.aruco.generateImageMarker(dictionary, tag_id, 512)
    # Outer white quiet zone: black-border square is exactly .20 m; full board .25 m.
    image = cv2.copyMakeBorder(marker, 64, 64, 64, 64, cv2.BORDER_CONSTANT, value=255)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), image):
        raise RuntimeError("failed to write tag texture")
    return output


def spawn_boards(prim_path, cfg, translation=None, orientation=None):
    from isaaclab.sim import SimulationContext
    from pxr import Gf, Sdf, UsdGeom, UsdShade

    stage = SimulationContext.instance().stage
    root = UsdGeom.Xform.Define(stage, prim_path)
    for tag_id in (0, 1):
        path = prim_path + f"/Tag{tag_id}"
        mesh = UsdGeom.Mesh.Define(stage, path)
        # Front face looks back along -X. Only the selected board is visible.
        x, y, z, s = 0.65, 0.0, 0.23, 0.125
        mesh.CreatePointsAttr(
            [
                Gf.Vec3f(x, y + s, z + s),
                Gf.Vec3f(x, y - s, z + s),
                Gf.Vec3f(x, y - s, z - s),
                Gf.Vec3f(x, y + s, z - s),
            ]
        )
        mesh.CreateFaceVertexCountsAttr([4])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        mesh.CreateDoubleSidedAttr(True)
        mesh.CreateSubdivisionSchemeAttr("none")
        uv = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
            "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex
        )
        uv.Set([Gf.Vec2f(0, 1), Gf.Vec2f(1, 1), Gf.Vec2f(1, 0), Gf.Vec2f(0, 0)])
        material = UsdShade.Material.Define(stage, path + "/Material")
        surface = UsdShade.Shader.Define(stage, path + "/Material/Surface")
        surface.CreateIdAttr("UsdPreviewSurface")
        surface.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0)
        surface.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
        texture = UsdShade.Shader.Define(stage, path + "/Material/Texture")
        texture.CreateIdAttr("UsdUVTexture")
        texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(cfg.texture_paths[tag_id])
        )
        texture.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
        reader = UsdShade.Shader.Define(stage, path + "/Material/UV")
        reader.CreateIdAttr("UsdPrimvarReader_float2")
        reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
        texture.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            reader.ConnectableAPI(), "result"
        )
        texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        surface.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            texture.ConnectableAPI(), "rgb"
        )
        surface.CreateOutput("surface", Sdf.ValueTypeNames.Token)
        material.CreateSurfaceOutput().ConnectToSource(surface.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
        if tag_id != cfg.active_tag:
            UsdGeom.Imageable(mesh).MakeInvisible()
    return root.GetPrim()


def configure_cameras(scene_cfg, mjcf, output_dir, *, tag_id=0, head_resolution=(640, 480)):
    import isaaclab.sim as sim_utils
    from isaaclab.assets import AssetBaseCfg
    from isaaclab.sensors import CameraCfg
    from isaaclab.utils import configclass
    from isaaclab_physx.renderers import IsaacRtxRendererCfg
    from scipy.spatial.transform import Rotation

    position, rotation = head_mount_from_source(mjcf)
    width, height = head_resolution
    head_path = (
        "{ENV_REGEX_NS}/Robot/Geometry/trunk_base/neck/neck_pitch_1/yaw_roll_motion/jaw_soft"
    )
    scene_cfg.head_camera = CameraCfg(
        prim_path=head_path + "/TeachingCamera",
        width=width,
        height=height,
        data_types=["rgb"],
        update_period=0.02,
        offset=CameraCfg.OffsetCfg(pos=position, rot=rotation, convention="world"),
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=18.0,
            horizontal_aperture=24.0,
            vertical_aperture=18.0,
            clipping_range=(0.01, 50.0),
        ),
        renderer_cfg=IsaacRtxRendererCfg(),
    )
    # A separately authored human-only view. No pose from this view enters policy.
    eye = np.array([0.55, 0.55, 0.38])
    target = np.array([0.02, 0, 0.13])
    forward = (target - eye) / np.linalg.norm(target - eye)
    left = np.cross([0, 0, 1], forward)
    left /= np.linalg.norm(left)
    up = np.cross(forward, left)
    quat = Rotation.from_matrix(np.column_stack([forward, left, up])).as_quat()
    scene_cfg.overview_camera = CameraCfg(
        prim_path="/World/OverviewCamera",
        width=640,
        height=480,
        data_types=["rgb"],
        update_period=0.02,
        offset=CameraCfg.OffsetCfg(pos=tuple(eye), rot=tuple(quat), convention="world"),
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=18.0,
            horizontal_aperture=24.0,
            vertical_aperture=18.0,
            clipping_range=(0.01, 50.0),
        ),
        renderer_cfg=IsaacRtxRendererCfg(),
    )
    textures = [
        str(make_tag_texture(i, Path(output_dir) / f"tag36h11_{i}.png").resolve()) for i in (0, 1)
    ]

    @configclass
    class BoardCfg(sim_utils.SpawnerCfg):
        func = spawn_boards
        texture_paths: list[str] = textures
        active_tag: int = tag_id

    scene_cfg.signal_board = AssetBaseCfg(prim_path="/World/Signals", spawn=BoardCfg())
    scene_cfg.light = AssetBaseCfg(
        prim_path="/World/TeachingLight", spawn=sim_utils.DomeLightCfg(intensity=2500.0)
    )
    return {
        "frame_id": "microduck_head_optical",
        "width": width,
        "height": height,
        "source": "authored teaching pinhole; not hardware calibration",
        "head_body": "jaw_soft",
        "local_translation_m": position,
        "local_quaternion_xyzw_world_convention": rotation,
        "tag_family": "tag36h11",
        "black_square_size_m": 0.2,
        "board_size_m": 0.25,
        "visible_tag_id": tag_id,
        "go_tag_id": 0,
        "stop_tag_id": 1,
    }
