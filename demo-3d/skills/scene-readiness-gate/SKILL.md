---
name: scene-readiness-gate
description: Qualify a generated physical scene for WorldStage intake, preserving source hashes and blocking unsupported robot-training claims.
---

# Scene readiness gate

Run `python3 studio/scene_gate.py examples/physical-world/scenario.json --output examples/physical-world/scene_gate.json` from `demo-3d/`. This validates metric coordinates, object IDs and dimensions, basic physics fields, and whether the current MJCF exporter accepts the scene. It records collision proxy mismatches and unmeasured parameters for human review. `structural_status=PASS` means the JSON and exporter contract passed; `robot_training_status` and `nvidia_simready_status` stay `NOT_RUN` until separate simulator and USD checks run.

The `/lab.html` panel calls `POST /api/lab/scene-gate` on its current scene. Recheck after adding an object; download the JSON report as an artifact. The API does not run a simulator.

For an external scene such as Hyper3D WorldGen, first map its exported independent objects into `worldstage.physical.v1` with meter-based transforms and explicit collision proxies. Add `--source source.json` with `schema=worldstage.scene_source.v1`, `producer`, `input_image_sha256`, `background_representation`, and one `{id, sha256}` record per object in `assets`. A 3DGS background is visual only in this contract. The actual WorldGen export schema and scene API are not publicly documented in the Rodin API reference; do not label a hand-authored or procedural scene as a WorldGen execution.
