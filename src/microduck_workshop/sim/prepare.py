"""Reapply pinned public training overrides without changing robot topology.

The downloaded source is read-only. Derived XML and converted USD are local cache
artifacts; meshes retain Pollen's CC BY-NC-SA 4.0 license.
"""

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .bam import BamM6


def prepare_training_mjcf(source, output_dir):
    source, output_dir = Path(source).resolve(), Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(source)
    root = tree.getroot()
    compiler = root.find("compiler")
    compiler.set("meshdir", str((source.parent / compiler.get("meshdir", ".")).resolve()))
    # The Lab indexed effort sink replaces MuJoCo's XML position drives. This is
    # an identity effort map; firmware control is the explicit BAM M6 pipeline.
    actuator = root.find("actuator")
    if actuator is not None:
        root.remove(actuator)
    selected = root.find(".//default[@class='chosen_actuator']/joint")
    for key, value in {
        "damping": BamM6.FRICTION_VISCOUS,
        "armature": BamM6.ARMATURE,
        "frictionloss": 0,
        "solreffriction": "-50000 -200",
        "solimpfriction": "0.99 0.9999 0.001 0.5 2",
    }.items():
        selected.set(key, str(value))
    for body in root.findall(".//worldbody//body"):
        count = 0
        for geom in body.findall("geom"):
            is_collision = geom.get("class") in ("collision", "self_collision_only")
            if geom.get("mesh") == "xl330" and is_collision:
                geom.set("name", f"{body.get('name')}_{count}_servo_collision")
                count += 1
            name = geom.get("name", "")
            if name.endswith("_collision"):
                geom.set("condim", "1")
            if name in ("left_foot_collision", "right_foot_collision"):
                geom.set("condim", "3")
                geom.set("priority", "1")
                geom.set("friction", "1.0 0.005 0.0001")
    output = output_dir / "microduck_bam.xml"
    tree.write(output, encoding="unicode", xml_declaration=True)
    receipt = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "derived_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "changes": [
            "absolute meshdir for local conversion",
            "remove XML PD; Lab effort sink",
            "BAM motor armature/passive friction + stiff friction constraints",
            "public training servo collision names/foot condim/friction",
        ],
        "body_count": len(root.findall(".//worldbody//body")),
        "joint_count": len(root.findall(".//worldbody//joint")),
    }
    (output_dir / "preparation.json").write_text(json.dumps(receipt, indent=2))
    return output
