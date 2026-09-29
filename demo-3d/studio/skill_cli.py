"""Run one WorldStage skill against an explicit, local run directory."""

from __future__ import annotations

import argparse
import json
import re

from pipeline import RUNS, _write, compose, intake, interactions, narrate, plan, verify


def load(run_id: str, name: str) -> dict:
    path = RUNS / run_id / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"missing prerequisite: {path}")
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=["intake", "plan", "compose", "interact", "narrate", "verify"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt")
    parser.add_argument("--template", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", args.run_id):
        raise SystemExit("invalid run id")
    if args.stage == "intake":
        if not args.prompt:
            raise SystemExit("--prompt required for intake")
        name, value = "intake", intake(args.prompt)
    elif args.stage == "plan":
        name, value = "plan", plan(load(args.run_id, "intake"), not args.template)
    elif args.stage == "compose":
        name, value = "scene", compose(load(args.run_id, "plan"))
    elif args.stage == "interact":
        name, value = "interactions", interactions(load(args.run_id, "scene"))
    elif args.stage == "narrate":
        name, value = "story", narrate(load(args.run_id, "plan"), load(args.run_id, "scene"))
    else:
        name, value = "evaluation", verify(load(args.run_id, "scene"), load(args.run_id, "interactions"), load(args.run_id, "story"))
    path = RUNS / args.run_id / f"{name}.json"
    digest = _write(path, value)
    print(json.dumps({"stage": args.stage, "path": str(path), "sha256": digest, "status": value.get("status", "complete")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
