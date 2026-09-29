"""Audit browser exploration as a source of robot-task candidates, never robot demonstrations."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pipeline import ROOT, RUNS, _write
from scene_gate import qualify


RISK_CODES = {"scale_uncertain", "collision_proxy", "friction_unmeasured", "path_blocked", "avatar_dynamics_unverified"}
CONTROL_SOURCES = {"keyboard", "clicked_goal", "scripted_patrol", "idle", "unknown"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _validate(trajectory: Any) -> list[dict]:
    if not isinstance(trajectory, dict) or trajectory.get("schema") not in {"worldstage.proxy_trajectory.v2", "worldstage.proxy_trajectory.v3"}:
        raise ValueError("expected a WorldStage browser proxy trajectory")
    if trajectory.get("simulation_engine") != "rapier3d_browser" or trajectory.get("robot_control") != "human_direction_to_kinematic_collision_proxy":
        raise ValueError("unsupported trajectory source or control contract")
    if not re.fullmatch(r"[0-9a-f]{64}", str(trajectory.get("source_urdf_sha256", ""))):
        raise ValueError("source URDF SHA-256 required")
    known_urdf_hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in
                         (ROOT / "public/robots/S10-source.urdf", ROOT / "public/robots/TurtleBot3-Burger-source.urdf")}
    if trajectory["source_urdf_sha256"] not in known_urdf_hashes:
        raise ValueError("source URDF SHA-256 does not match a packaged robot")
    frames = trajectory.get("frames")
    if not isinstance(frames, list) or not 2 <= len(frames) <= 12000:
        raise ValueError("2 to 12000 frames required")
    previous_time = -1.0
    previous_contacts = -1
    for i, frame in enumerate(frames):
        if not isinstance(frame, dict):
            raise ValueError(f"frame {i} must be an object")
        t, pos, direction, contacts = (frame.get(k) for k in ("t_s", "position_m", "human_command_direction", "proxy_contacts_total"))
        if not _number(t) or t <= previous_time or t > 7200:
            raise ValueError(f"frame {i} has invalid time")
        if not isinstance(pos, list) or len(pos) != 3 or not all(_number(v) and abs(v) <= 80 for v in pos):
            raise ValueError(f"frame {i} has invalid position")
        if not isinstance(direction, list) or len(direction) != 2 or not all(_number(v) and abs(v) <= 1.01 for v in direction):
            raise ValueError(f"frame {i} has invalid command direction")
        if not isinstance(contacts, int) or isinstance(contacts, bool) or contacts < previous_contacts:
            raise ValueError(f"frame {i} has invalid contact counter")
        source = frame.get("control_source", "unknown")
        if source not in CONTROL_SOURCES:
            raise ValueError(f"frame {i} has invalid control source")
        previous_time, previous_contacts = t, contacts
    events = trajectory.get("events", [])
    if not isinstance(events, list) or len(events) > 30000 or any(not isinstance(event, dict) for event in events):
        raise ValueError("invalid events")
    return frames


def _hotspots(events: list[dict]) -> list[dict]:
    cells: dict[tuple[int, int], int] = {}
    for event in events:
        if event.get("type") != "proxy_collision":
            continue
        pos = event.get("position")
        if not isinstance(pos, list) or len(pos) != 2 or not all(_number(v) for v in pos):
            continue
        key = (math.floor(pos[0] / 2), math.floor(pos[1] / 2))
        cells[key] = cells.get(key, 0) + max(1, min(int(event.get("count", 1)), 20))
    return [{"cell_origin_m": [x * 2, y * 2], "cell_size_m": 2, "contacts": count}
            for (x, y), count in sorted(cells.items(), key=lambda row: -row[1])[:5]]


def _metrics(frames: list[dict], events: list[dict]) -> dict:
    path = 0.0
    commanded = 0
    human = 0
    scripted = 0
    stuck_windows = 0
    stuck_start: int | None = None
    for i, frame in enumerate(frames):
        source = frame.get("control_source", "unknown")
        if source in {"keyboard", "clicked_goal"}:
            human += 1
        if source == "scripted_patrol":
            scripted += 1
        moving_command = math.hypot(*frame["human_command_direction"]) > 0.5
        commanded += int(moving_command)
        if i:
            earlier = frames[i - 1]["position_m"]
            current = frame["position_m"]
            path += math.dist(earlier[:2], current[:2])
        if moving_command:
            if stuck_start is None:
                stuck_start = i
            if frame["t_s"] - frames[stuck_start]["t_s"] >= 1.0:
                delta = math.dist(frames[stuck_start]["position_m"][:2], frame["position_m"][:2])
                if delta < 0.1:
                    stuck_windows += 1
                stuck_start = i
        else:
            stuck_start = None
    net = math.dist(frames[0]["position_m"][:2], frames[-1]["position_m"][:2])
    contacts = frames[-1]["proxy_contacts_total"] - frames[0]["proxy_contacts_total"]
    return {"duration_s": round(frames[-1]["t_s"] - frames[0]["t_s"], 2),
            "sample_count": len(frames), "path_length_m": round(path, 3), "net_displacement_m": round(net, 3),
            "path_efficiency": round(net / path, 3) if path > 0 else None,
            "proxy_contact_count": contacts, "contacts_per_m": round(contacts / path, 2) if path > 0 else None,
            "commanded_samples": commanded, "human_control_samples": human, "scripted_control_samples": scripted,
            "control_source_known_fraction": round((human + scripted + sum(f.get("control_source") == "idle" for f in frames)) / len(frames), 3),
            "stuck_windows_1s": stuck_windows, "contact_hotspots": _hotspots(events)}


def _model_review(summary: dict) -> dict:
    base, model = os.getenv("NEMOTRON_BASE_URL", "").rstrip("/"), os.getenv("NEMOTRON_MODEL", "")
    if not base or "nemotron" not in model.lower():
        return {"status": "NOT_RUN", "reason": "Nemotron service not configured"}
    instruction = ("You review a robot browser proxy episode. Return only JSON with keys "
                   "scenario_risks (0 to 3 codes from scale_uncertain, collision_proxy, friction_unmeasured, "
                   "path_blocked, avatar_dynamics_unverified), suggested_robot_task (max 120 chars), "
                   "next_probe (max 160 chars). Choose risks only from supported_risks in the input. "
                   "Use only supplied evidence; never claim sim2sim, sim2real, "
                   "robot policy quality, or physical calibration has passed. The trace is a kinematic proxy.")
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": instruction},
                      {"role": "user", "content": json.dumps(summary, ensure_ascii=False)}],
                       "temperature": 0.1, "max_tokens": 400}).encode()
    try:
        request = urllib.request.Request(base + "/chat/completions", data=body,
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=35) as response:
            content = json.load(response)["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise ValueError("no JSON object")
        raw = json.loads(match.group(0))
        if not isinstance(raw, dict) or not isinstance(raw.get("scenario_risks"), list):
            raise ValueError("invalid model schema")
        supported = set(summary["supported_risks"])
        risks = [item for item in raw["scenario_risks"] if item in RISK_CODES and item in supported][:3]
        rejected = [item for item in raw["scenario_risks"] if item in RISK_CODES and item not in supported]
        task = str(raw.get("suggested_robot_task", ""))[:120]
        probe = str(raw.get("next_probe", ""))[:160]
        if re.search(r"(sim2real|sim2sim|实机|机器人训练).{0,12}(已通过|已完成|ready|passed)", task + " " + probe, re.I):
            return {"status": "REJECTED_UNSUPPORTED_CLAIM", "model": model,
                    "reason": "model claimed an unverified transfer gate", "advisory_only": True,
                    "candidate_sha256": _digest(raw)}
        return {"status": "PASS", "model": model, "scenario_risks": risks,
                "unsupported_risks_rejected": rejected,
                "suggested_robot_task": task, "next_probe": probe,
                "advisory_only": True, "candidate_sha256": _digest(raw)}
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "ERROR", "model": model, "reason": type(exc).__name__, "advisory_only": True}


def audit_episode(payload: dict, allow_model: bool = True) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    scenario, trajectory = payload.get("scenario"), payload.get("trajectory")
    if not isinstance(scenario, dict) or not isinstance(trajectory, dict):
        raise ValueError("scenario and trajectory are required")
    frames = _validate(trajectory)
    scene_robot, trace_robot = scenario.get("robot"), trajectory.get("robot")
    if not isinstance(scene_robot, dict) or not isinstance(trace_robot, dict) or scene_robot.get("source_urdf_sha256") != trajectory["source_urdf_sha256"] or scene_robot.get("name") != trace_robot.get("name"):
        raise ValueError("scenario robot and trajectory robot identity differ")
    gate = qualify(scenario)
    events = trajectory.get("events", [])
    metrics = _metrics(frames, events)
    flags = []
    if gate["structural_status"] != "PASS":
        flags.append("scene_structure_failed")
    if gate["robot_training_status"] != "PASS":
        flags.append("scene_not_training_ready")
    if metrics["proxy_contact_count"] > 0:
        flags.append("proxy_contacts_observed")
    if metrics["stuck_windows_1s"]:
        flags.append("commanded_but_stuck")
    if metrics["control_source_known_fraction"] < 1:
        flags.append("control_source_partly_unknown")
    visual_source = scenario.get("visual_source")
    manifest_reference_status = "NOT_RUN"
    if isinstance(visual_source, dict) and visual_source.get("provider") == "Hyper3D WorldGen":
        manifest = json.loads((ROOT / "public/worldgen/manifest.json").read_text())
        manifest_reference_status = "PASS" if (visual_source.get("original_export_sha256") == manifest["original_export_sha256"]
            and visual_source.get("source_image_sha256") == manifest["source_image_sha256"]
            and visual_source.get("asset_count") == manifest["asset_count"]) else "FAIL"
        if manifest_reference_status == "FAIL":
            flags.append("worldgen_manifest_reference_mismatch")
    scene_hash = _digest(scenario)
    trace_hash = _digest(trajectory)
    summary = {"avatar": trajectory.get("robot", {}).get("name") if isinstance(trajectory.get("robot"), dict) else None,
               "scene_gate": {"structural_status": gate["structural_status"], "robot_training_status": gate["robot_training_status"],
                              "issue_codes": sorted({item["code"] for item in gate["issues"]})},
               "metrics": metrics, "story_clues": trajectory.get("story_clues", []), "truth_route": trajectory.get("truth_route"),
               "worldgen_physics_status": (trajectory.get("worldgen_source") or {}).get("physics_status") if isinstance(trajectory.get("worldgen_source"), dict) else None}
    supported_risks = {"avatar_dynamics_unverified"}
    codes = set(summary["scene_gate"]["issue_codes"])
    if summary["worldgen_physics_status"] and "metric_unverified" in summary["worldgen_physics_status"]:
        supported_risks.add("scale_uncertain")
    if codes & {"collision_proxy_mismatch", "collision_proxy_unverified", "engine_collision_mismatch", "mesh_collision_fallback"}:
        supported_risks.add("collision_proxy")
    if "unmeasured_physics" in codes:
        supported_risks.add("friction_unmeasured")
    if metrics["stuck_windows_1s"]:
        supported_risks.add("path_blocked")
    summary["supported_risks"] = sorted(supported_risks)
    model_review = _model_review(summary) if allow_model else {"status": "NOT_RUN", "reason": "template/offline audit requested"}
    task_specs = []
    for event in events:
        target = event.get("target_position_m")
        if event.get("type") != "navigation_goal" or event.get("source") != "human_click":
            continue
        if not isinstance(target, list) or len(target) != 2 or not all(_number(v) and abs(v) <= 40 for v in target):
            continue
        event_t = event.get("time_s", 0)
        start = min(frames, key=lambda frame: abs(frame["t_s"] - event_t)) if _number(event_t) else frames[0]
        task_specs.append({"task_type": "navigate_to_human_selected_goal", "status": "CANDIDATE_ONLY",
                           "start_root_position_m": start["position_m"], "goal_xy_m": target,
                           "goal_radius_m": 0.5, "goal_source": "human_click", "goal_time_s": event_t})
        if len(task_specs) == 10:
            break
    transitions = []
    for a, b in zip(frames, frames[1:]):
        source = b.get("control_source", "unknown")
        transitions.append({"t_s": a["t_s"], "dt_s": round(b["t_s"] - a["t_s"], 4),
                            "root_position_m": a["position_m"], "next_root_position_m": b["position_m"],
                            "direction_intent": b["human_command_direction"], "intent_source": source,
                            "human_intent": source in {"keyboard", "clicked_goal"},
                            "proxy_contact_delta": b["proxy_contacts_total"] - a["proxy_contacts_total"]})
    candidate = {"schema": "worldstage.sim_episode_candidate.v1", "data_tier": "browser_kinematic_proxy",
                 "usage": "scenario_selection_and_goal_inference_only", "policy_training_ready": False,
                 "sim2sim_ready": False, "sim2real_ready": False, "human_review_required": True,
                 "scenario_sha256": scene_hash, "trajectory_sha256": trace_hash,
                 "source_urdf_sha256": trajectory["source_urdf_sha256"],
                 "worldgen_source": trajectory.get("worldgen_source"), "avatar": summary["avatar"],
                 "transitions": transitions, "task_events": [e for e in events if e.get("type") != "proxy_collision"][:2000],
                 "task_specs": task_specs, "task_spec_status": "CANDIDATE_ONLY" if task_specs else "NEEDS_EXPLICIT_HUMAN_GOAL",
                 "hotspot_probe_candidates": metrics["contact_hotspots"],
                 "sim2sim_replay_contract": {"status": "NOT_RUN", "engines_required": ["MuJoCo", "Isaac Sim"],
                    "robot_mode": "actuated_urdf", "same_scene_and_initial_conditions": True,
                    "required_recordings": ["joint_position", "joint_velocity", "joint_torque_or_command", "body_pose", "contact_points", "task_outcome"],
                    "compare": ["goal_completion", "falls", "contacts", "trajectory_deviation"]},
                 "next_gate": "calibrate source units and contacts, replay same goals with actuated URDF in two physics engines, then compare real robot data"}
    report = {"schema": "worldstage.behavior_audit.v1", "scenario_sha256": scene_hash,
              "trajectory_sha256": trace_hash, "source_urdf_sha256": trajectory["source_urdf_sha256"],
              "deterministic": {"status": "PASS" if gate["structural_status"] == "PASS" and manifest_reference_status != "FAIL" else "FAIL",
                                "metrics": metrics, "flags": flags, "scene_gate_status": gate["structural_status"],
                                "worldgen_manifest_reference_status": manifest_reference_status,
                                "robot_training_status": gate["robot_training_status"],
                                "scene_issue_codes": summary["scene_gate"]["issue_codes"]},
              "nemotron_review": model_review, "candidate_tier": candidate["data_tier"],
              "sim2sim_status": "NOT_RUN", "sim2real_status": "NOT_RUN"}
    return {"report": report, "candidate": candidate}


def save_audit(payload: dict, result: dict) -> dict:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    run_id = f"episode-{stamp}-{result['report']['trajectory_sha256'][:8]}"
    folder = RUNS / run_id
    if folder.exists():
        run_id += f"-{os.urandom(2).hex()}"
        folder = RUNS / run_id
    files = {"scenario.json": payload["scenario"], "trajectory.json": payload["trajectory"],
             "audit.json": result["report"], "candidate.json": result["candidate"]}
    hashes = {name: _write(folder / name, value) for name, value in files.items()}
    _write(folder / "manifest.json", {"schema": "worldstage.episode_manifest.v1", "run_id": run_id,
                                       "status": "COMPLETE", "artifacts_sha256": hashes,
                                       "data_tier": "browser_kinematic_proxy"})
    return {**result, "run_id": run_id, "artifacts_sha256": hashes}
