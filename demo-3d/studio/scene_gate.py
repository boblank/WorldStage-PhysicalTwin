"""Task-level intake gate for generated WorldStage scenes.

This checks the JSON/MJCF contract and reports assumptions. It does not certify
NVIDIA SimReady, robot dynamics, or real-world transfer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from robot_world import KIND, scenario_mjcf


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def qualify(scenario: Any, source: dict[str, Any] | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    def issue(level: str, code: str, detail: str, object_id: str = "") -> None:
        item = {"level": level, "code": code, "detail": detail}
        if object_id:
            item["object_id"] = object_id
        issues.append(item)

    if not isinstance(scenario, dict):
        scenario = {}
        issue("error", "scenario_not_object", "Scene must be a JSON object")
    if scenario.get("schema") != "worldstage.physical.v1":
        issue("error", "schema", "Expected worldstage.physical.v1")
    if scenario.get("coordinate_system") != "z_up" or scenario.get("units") != "m_kg_s":
        issue("error", "frame_units", "Expected z_up and m_kg_s")
    if scenario.get("gravity_m_s2") != [0, 0, -9.81]:
        issue("error", "gravity", "Expected [0, 0, -9.81] m/s²")
    ground = scenario.get("ground")
    if not isinstance(ground, dict) or not isinstance(ground.get("size_m"), list) or len(ground["size_m"]) != 2 or not all(_finite_number(v) and v > 0 for v in ground["size_m"]):
        issue("error", "ground", "Positive ground size is required")
    obstacles = scenario.get("obstacles")
    if not isinstance(obstacles, list) or not obstacles:
        obstacles = []
        issue("error", "obstacles", "At least one object is required")

    ids: set[str] = set()
    for index, obj in enumerate(obstacles):
        if not isinstance(obj, dict):
            issue("error", "object_type", f"Object {index} must be a JSON object")
            continue
        ident = obj.get("id")
        label = ident if isinstance(ident, str) else f"index-{index}"
        if not isinstance(ident, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+", ident) or ident in ids:
            issue("error", "object_id", "Object ID must be unique and ASCII safe", label)
        else:
            ids.add(ident)
        if obj.get("kind") not in KIND:
            issue("error", "kind", "Unsupported geometry kind", label)
        position, size = obj.get("position"), obj.get("size")
        if not isinstance(position, list) or len(position) != 3 or not all(_finite_number(v) and abs(v) <= 40 for v in position):
            issue("error", "position", "Position must be finite and within the 80 m world", label)
        if not isinstance(size, list) or len(size) != 3 or not all(_finite_number(v) and 0 < v <= 80 for v in size):
            issue("error", "size", "Size must be finite and positive", label)
        if not _finite_number(obj.get("yaw", 0)):
            issue("error", "yaw", "Yaw must be finite", label)
        mass, friction = obj.get("mass_kg"), obj.get("friction")
        if not _finite_number(mass) or mass < 0:
            issue("error", "mass", "Mass must be nonnegative", label)
        if not _finite_number(friction) or not 0 <= friction <= 2:
            issue("error", "friction", "Friction must be in the supported [0, 2] range", label)
        if obj.get("kind") in {"ramp", "crystal", "building"}:
            issue("review", "collision_proxy_mismatch", "MJCF export uses a box proxy; inspect contact geometry before robot evaluation", label)
        if obj.get("collision_proxy_status") not in {None, "measured", "mesh_verified"}:
            detail = "Source triangles are loaded, but contact behaviour and metric scale are not validated" if obj.get("collision_proxy_status") == "source_glb_trimesh_rapier" else "Collision is an estimated proxy, not the exported visual mesh"
            issue("review", "collision_proxy_unverified", detail, label)
        if obj.get("collision_proxy_status") == "source_glb_trimesh_rapier":
            issue("review", "engine_collision_mismatch", "Rapier uses source GLB triangles, while MJCF export still uses a primitive proxy", label)
        if obj.get("physical_parameter_status", scenario.get("parameter_status")) not in {"measured", "calibrated"}:
            issue("review", "unmeasured_physics", "Mass/friction are estimates or design assumptions", label)

    if source is not None:
        if not isinstance(source, dict) or source.get("schema") != "worldstage.scene_source.v1":
            issue("error", "source_schema", "Source receipt must use worldstage.scene_source.v1")
        else:
            if source.get("producer") == "Hyper3D WorldGen" and not re.fullmatch(r"[0-9a-f]{64}", str(source.get("input_image_sha256", ""))):
                issue("error", "input_image_hash", "WorldGen image source requires SHA-256")
            if source.get("producer") == "Hyper3D WorldGen" and source.get("source_units") == "unknown":
                issue("review", "unit_scale_unverified", "WorldGen GLB units have not been calibrated to metres")
            assets = source.get("assets")
            if not isinstance(assets, list) or len(assets) != len(ids) or {a.get("id") for a in assets if isinstance(a, dict)} != ids:
                issue("error", "asset_id_coverage", "Source asset IDs must match scene object IDs exactly")
            else:
                for asset in assets:
                    if not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("sha256", ""))):
                        issue("error", "asset_hash", "Asset SHA-256 is required", str(asset.get("id", "")))
                issue("review", "asset_hash_declared_only", "Asset SHA values are declared in the receipt; check them against exported files")
            if source.get("background_representation") == "3dgs":
                issue("review", "background_visual_only", "3DGS has no verified collision in this contract")
    else:
        issue("review", "source_receipt_missing", "No source image/asset receipt supplied")
    visual_source = scenario.get("visual_source")
    if isinstance(visual_source, dict) and visual_source.get("provider") == "Hyper3D WorldGen":
        if visual_source.get("source_unit_status") != "metric_measured":
            issue("review", "unit_scale_unverified", "WorldGen visual scale has no measured metre reference")
        if visual_source.get("box_fallback_count", 0):
            issue("review", "mesh_collision_fallback", "At least one WorldGen GLB used a bounding box after mesh-collider failure")

    mjcf_exportable = False
    if not any(item["level"] == "error" for item in issues):
        try:
            scenario_mjcf(scenario)
            mjcf_exportable = True
        except (ValueError, TypeError, KeyError) as exc:
            issue("error", "mjcf_export", f"MJCF export failed: {type(exc).__name__}")

    valid = not any(item["level"] == "error" for item in issues)
    return {
        "schema": "worldstage.scene_gate.v1",
        "structural_status": "PASS" if valid else "FAIL",
        "mjcf_exportable": mjcf_exportable,
        "robot_training_status": "BLOCKED" if valid and any(item["code"] in {"engine_collision_mismatch", "mesh_collision_fallback"} for item in issues) else "NOT_RUN" if valid else "BLOCKED",
        "nvidia_simready_status": "NOT_RUN",
        "source_producer": source.get("producer") if isinstance(source, dict) else None,
        "object_count": len(obstacles),
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--source", type=Path, help="Optional source/asset receipt JSON")
    parser.add_argument("--output", type=Path, help="Write a gate receipt JSON")
    args = parser.parse_args()
    scenario_bytes = args.scenario.read_bytes()
    source_bytes = args.source.read_bytes() if args.source else None
    report = qualify(json.loads(scenario_bytes), json.loads(source_bytes) if source_bytes else None)
    if source_bytes:
        source_data = json.loads(source_bytes)
        asset_issues = []
        verified = 0
        for asset in source_data.get("assets", []):
            if not isinstance(asset, dict) or not asset.get("file"):
                continue
            asset_path = (args.source.parent / asset["file"]).resolve()
            if not asset_path.is_file():
                asset_issues.append({"level": "error", "code": "asset_missing", "detail": "Exported asset file is missing", "object_id": str(asset.get("id", ""))})
            elif hashlib.sha256(asset_path.read_bytes()).hexdigest() != asset.get("sha256"):
                asset_issues.append({"level": "error", "code": "asset_hash_mismatch", "detail": "Exported asset hash does not match receipt", "object_id": str(asset.get("id", ""))})
            else:
                verified += 1
        report["asset_files_verified"] = verified
        if verified == len(source_data.get("assets", [])) and not asset_issues:
            report["issues"] = [item for item in report["issues"] if item["code"] != "asset_hash_declared_only"]
        report["issues"].extend(asset_issues)
        if asset_issues:
            report["structural_status"] = "FAIL"
            report["robot_training_status"] = "BLOCKED"
    report["scenario_sha256"] = hashlib.sha256(scenario_bytes).hexdigest()
    report["source_sha256"] = hashlib.sha256(source_bytes).hexdigest() if source_bytes else None
    result = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)
    print(result, end="")
    raise SystemExit(0 if report["structural_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
