"""Frozen positive and negative cases for browser-trace curation; no live model claims."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path

from behavior_audit import _digest, audit_episode
from pipeline import ROOT, _write
from robot_world import base_scenario


def _real_browser_case() -> dict:
    folder = ROOT / "examples/skill-benchmark"
    receipt = json.loads((folder / "browser_e2e_receipt.json").read_text())
    return json.loads(gzip.decompress((folder / receipt["trajectory_file"]).read_bytes()))


def _synthetic_case(stuck: bool) -> dict:
    base = _real_browser_case()
    base["schema"] = "worldstage.proxy_trajectory.v3"
    base["events"] = []
    base["frames"] = [{"t_s": round(i * .1 + .1, 2), "position_m": [0 if stuck else i * .05, 0, .42],
                       "human_command_direction": [1, 0], "control_source": "keyboard",
                       "proxy_contacts_total": 0} for i in range(24)]
    return base


def run() -> dict:
    scenario = base_scenario()
    cases = []

    def record(name: str, good: bool, detail: str) -> None:
        cases.append({"case": name, "status": "PASS" if good else "FAIL", "detail": detail})

    real = audit_episode({"scenario": scenario, "trajectory": _real_browser_case()}, allow_model=False)
    m = real["report"]["deterministic"]["metrics"]
    record("recorded_browser_trace", m["sample_count"] >= 100 and m["proxy_contact_count"] > 0
           and real["candidate"]["policy_training_ready"] is False and real["report"]["nemotron_review"]["status"] == "NOT_RUN",
           "recorded browser route produces proxy contacts and stays outside policy-training tier")

    folder = ROOT / "examples/skill-benchmark"
    receipt = json.loads((folder / "behavior_ui_receipt.json").read_text())
    compressed = (folder / receipt["fixture_file"]).read_bytes()
    raw = gzip.decompress(compressed)
    segments = json.loads(raw)["segments"]
    split_ok = (hashlib.sha256(compressed).hexdigest() == receipt["fixture_sha256"]
        and hashlib.sha256(raw).hexdigest() == receipt["decompressed_sha256"]
        and [len(segment["scenario"]["obstacles"]) for segment in segments] == [18, 19]
        and segments[1]["trajectory"]["events"][0]["reason"] == "object_generated"
        and all(segment["report"]["deterministic"]["worldgen_manifest_reference_status"] == "PASS"
                and segment["report"]["scenario_sha256"] == _digest(segment["scenario"])
                and segment["report"]["trajectory_sha256"] == _digest(segment["trajectory"])
                and segment["candidate"]["policy_training_ready"] is False for segment in segments))
    record("recorded_scene_revision_split", split_ok,
           "actual browser run archived an 18-object episode before adding a ramp and started a 19-object episode")

    stuck = audit_episode({"scenario": scenario, "trajectory": _synthetic_case(True)}, allow_model=False)
    moving = audit_episode({"scenario": scenario, "trajectory": _synthetic_case(False)}, allow_model=False)
    record("stuck_vs_progress", stuck["report"]["deterministic"]["metrics"]["stuck_windows_1s"] > 0
           and moving["report"]["deterministic"]["metrics"]["stuck_windows_1s"] == 0,
           "one-second commanded-no-progress window detected; progress control has none")
    record("human_intent_provenance", moving["candidate"]["transitions"][0]["human_intent"] is True
           and moving["report"]["deterministic"]["metrics"]["control_source_known_fraction"] == 1,
           "keyboard intent is labeled while unknown legacy control is not guessed")

    goal_case = _synthetic_case(False)
    goal_case["events"] = [{"time_s": .5, "type": "navigation_goal", "source": "human_click", "target_position_m": [2, 1]}]
    goal = audit_episode({"scenario": scenario, "trajectory": goal_case}, allow_model=False)["candidate"]
    record("explicit_goal_to_replay_task", len(goal["task_specs"]) == 1 and goal["task_specs"][0]["goal_xy_m"] == [2, 1]
           and goal["task_specs"][0]["status"] == "CANDIDATE_ONLY" and not moving["candidate"]["task_specs"],
           "human click becomes a simulator task candidate; movement alone does not invent a goal")

    invalid = copy.deepcopy(_synthetic_case(False))
    invalid["frames"][4]["t_s"] = invalid["frames"][3]["t_s"]
    try:
        audit_episode({"scenario": scenario, "trajectory": invalid}, allow_model=False)
        rejected = False
    except ValueError:
        rejected = True
    record("nonmonotonic_time_rejected", rejected, "duplicate timestamp cannot become a training candidate")

    wrong_robot = copy.deepcopy(scenario)
    wrong_robot["robot"]["source_urdf_sha256"] = "0" * 64
    try:
        audit_episode({"scenario": wrong_robot, "trajectory": _synthetic_case(False)}, allow_model=False)
        robot_rejected = False
    except ValueError:
        robot_rejected = True
    record("robot_identity_mismatch_rejected", robot_rejected, "scene robot and episode URDF must be the same source")

    bad_scene = copy.deepcopy(scenario)
    bad_scene["obstacles"][1]["id"] = bad_scene["obstacles"][0]["id"]
    scene_result = audit_episode({"scenario": bad_scene, "trajectory": _synthetic_case(False)}, allow_model=False)
    record("scene_gate_cannot_be_overridden", scene_result["report"]["deterministic"]["status"] == "FAIL"
           and scene_result["candidate"]["sim2sim_ready"] is False and scene_result["candidate"]["sim2real_ready"] is False,
           "duplicate object ID blocks structural gate and transfer claims")

    return {"schema": "worldstage.behavior_benchmark.v1", "scope": "offline_frozen_browser_and_synthetic_negative_cases",
            "model_quality": "NOT_RUN", "robot_training": "NOT_RUN", "cases": cases,
            "passed": sum(case["status"] == "PASS" for case in cases), "total": len(cases),
            "status": "PASS" if all(case["status"] == "PASS" for case in cases) else "FAIL"}


def run_live() -> dict:
    """Opt-in model quality gate; never inferred from the offline Skill benchmark."""
    if not os.getenv("NEMOTRON_BASE_URL") or "nemotron" not in os.getenv("NEMOTRON_MODEL", "").lower():
        return {"schema": "worldstage.behavior_model_benchmark.v1", "status": "NOT_RUN",
                "reason": "set NEMOTRON_BASE_URL and NEMOTRON_MODEL for a live run"}
    scenario = base_scenario()
    cases = []
    for name, trajectory, expected_path_blocked in [
        ("recorded_browser", _real_browser_case(), None),
        ("commanded_stuck", _synthetic_case(True), True),
        ("commanded_progress", _synthetic_case(False), False),
    ]:
        result = audit_episode({"scenario": scenario, "trajectory": trajectory}, allow_model=True)
        review = result["report"]["nemotron_review"]
        good = review["status"] == "PASS" and bool(review.get("next_probe")) and not review.get("unsupported_risks_rejected")
        if expected_path_blocked is not None:
            good &= ("path_blocked" in review.get("scenario_risks", [])) == expected_path_blocked
        cases.append({"case": name, "status": "PASS" if good else "FAIL",
                      "model_status": review["status"], "scenario_risks": review.get("scenario_risks", []),
                      "candidate_sha256": review.get("candidate_sha256"),
                      "deterministic_status": result["report"]["deterministic"]["status"]})
    return {"schema": "worldstage.behavior_model_benchmark.v1", "model": os.getenv("NEMOTRON_MODEL"),
            "scope": "three_episode_risk_and_next_probe_cases_not_robot_transfer",
            "cases": cases, "passed": sum(item["status"] == "PASS" for item in cases), "total": len(cases),
            "status": "PASS" if all(item["status"] == "PASS" for item in cases) else "FAIL",
            "robot_training": "NOT_RUN"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "examples/skill-benchmark/behavior_report.json")
    parser.add_argument("--live", action="store_true", help="Run three actual Nemotron audit cases; requires model environment")
    args = parser.parse_args()
    result = run_live() if args.live else run()
    _write(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(result["status"] != "PASS")


if __name__ == "__main__":
    main()
