"""Convert a verified Hyper3D WorldGen mesh export into review-only WorldStage proxies.

The GLB unit is *assumed* to be a metre. Visual geometry, mass, friction,
collision and robot traversability are not certified by this conversion.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import struct
from pathlib import Path


OBJECTS = (
    ("stairs", "four-step stair", "box", "stone", 0.0, 0.8),
    ("block-back", "rear stone block", "box", "stone", 0.0, 0.8),
    ("block-right", "right stone block", "box", "stone", 0.0, 0.8),
    ("block-front", "front stone block", "box", "stone", 0.0, 0.8),
    ("ramp", "wooden ramp", "ramp", "wood", 0.0, 0.6),
    ("ball", "red foam ball", "sphere", "warning", 0.5, 0.6),
    ("rail", "rear safety rail", "box", "metal", 0.0, 0.7),
)


def bounds_from_glb(path: Path, transform: list[list[float]]) -> tuple[list[float], list[float]]:
    raw = path.read_bytes()
    if raw[:4] != b"glTF" or struct.unpack_from("<I", raw, 8)[0] != len(raw):
        raise ValueError(f"Invalid GLB: {path}")
    size, kind = struct.unpack_from("<I4s", raw, 12)
    if kind != b"JSON":
        raise ValueError(f"Missing GLB JSON chunk: {path}")
    gltf = json.loads(raw[20 : 20 + size])
    positions = []
    for mesh in gltf["meshes"]:
        for primitive in mesh["primitives"]:
            accessor = gltf["accessors"][primitive["attributes"]["POSITION"]]
            positions.extend(itertools.product(*zip(accessor["min"], accessor["max"])))
    if not positions:
        raise ValueError(f"No POSITION bounds: {path}")
    points = [
        [sum(transform[i][j] * point[j] for j in range(3)) + transform[i][3] for i in range(3)]
        for point in positions
    ]
    return [min(p[i] for p in points) for i in range(3)], [max(p[i] for p in points) for i in range(3)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_dir", type=Path, help="Directory containing pack/separated_objects/glb")
    parser.add_argument("--input-image", type=Path, required=True)
    parser.add_argument("--workspace-url", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.export_dir / "pack/separated_objects/glb"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    obstacles, assets = [], []
    for index, (ident, name, kind, material, mass, friction) in enumerate(OBJECTS):
        directory = root / f"object_{index:04d}"
        mesh = directory / "model_pbr.glb"
        matrix = json.loads((directory / "transform_matrix.json").read_text())
        lo, hi = bounds_from_glb(mesh, matrix)
        extent = [hi[i] - lo[i] for i in range(3)]
        # WorldGen is Y-up; WorldStage JSON is Z-up. Place each visual proxy on
        # the ground because the source floor origin and metric calibration are unknown.
        obstacles.append({
            "id": ident,
            "name": name,
            "kind": kind,
            "position": [round((lo[0] + hi[0]) / 2, 4), round((lo[2] + hi[2]) / 2, 4), round(extent[1] / 2, 4)],
            "size": [round(extent[0], 4), round(extent[2], 4), round(extent[1], 4)],
            "yaw": 0,
            "mass_kg": mass,
            "friction": friction,
            "material": material,
            "physical_parameter_status": "estimated_from_visual_mesh",
            "collision_proxy_status": "bounding_box_estimate",
            "worldgen_object_index": index,
        })
        assets.append({
            "id": ident,
            "sha256": hashlib.sha256(mesh.read_bytes()).hexdigest(),
            "file": os.path.relpath(mesh.resolve(), args.output_dir.resolve()),
            "transform_sha256": hashlib.sha256((directory / "transform_matrix.json").read_bytes()).hexdigest(),
        })
    scene = {
        "schema": "worldstage.physical.v1",
        "units": "m_kg_s",
        "coordinate_system": "z_up",
        "gravity_m_s2": [0, 0, -9.81],
        "parameter_status": "estimated_from_visual_mesh",
        "visual_generation": "Hyper3D WorldGen exported meshes",
        "ground": {"size_m": [16, 16], "friction": 0.8},
        "obstacles": obstacles,
    }
    source = {
        "schema": "worldstage.scene_source.v1",
        "producer": "Hyper3D WorldGen",
        "workspace_url": args.workspace_url,
        "input_image_sha256": hashlib.sha256(args.input_image.read_bytes()).hexdigest(),
        "input_image_file": os.path.relpath(args.input_image.resolve(), args.output_dir.resolve()),
        "background_representation": "none",
        "source_units": "unknown",
        "unit_conversion": "assumed 1 GLB unit = 1 metre; unverified",
        "assets": assets,
    }
    (args.output_dir / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "source.json").write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
