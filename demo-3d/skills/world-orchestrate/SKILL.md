---
name: world-orchestrate
description: Route a request through the creative or physical WorldStage skill chain, preserving source, simulator, and robot evidence boundaries.
---

# WorldStage orchestrator

For a creative 3D brief, run `world-intake → world-plan → world-compose → world-interact → world-narrate → world-verify`. Each step writes a versioned JSON artifact under `runs/<run-id>/`. Read `evaluation.json` and the model provenance before reporting completion. The interactive web route calls the same Python functions through `studio/server.py`.

For a robot scene request, run `nemotron-service-audit → robot-urdf-import → physical-world-author → scene-readiness-gate → physics-scenario-export → rollout-capture`. Keep the source URDF SHA, object provenance, scene JSON, gate report, MJCF, simulator result, and trajectory together under one episode ID. `studio/server.py` powers the browser route; `studio/verify_delivery.py` checks the bundled example. A gate PASS only admits a scene for further simulator inspection. MuJoCo/Isaac and real robot evidence must be recorded separately.

Run locally from the `demo-3d/` directory:

```bash
python3 studio/pipeline.py "一座会回应访客的夜光森林" --template
```

The `--template` mode creates a reproducible demo with `provenance.mode=template`. Without it, the planner tries an OpenAI-compatible local service configured through `NEMOTRON_BASE_URL` and `NEMOTRON_MODEL`. If the model is unavailable or returns invalid JSON, it records the fallback reason. Never describe a template run as model inference.

For the physical path, use `/lab.html` to generate and export the current scene, then run `python3 studio/scene_gate.py scenario.json --output scene_gate.json` and `python3 studio/verify_delivery.py`. The included `examples/physical-world/s10_unactuated_rollout.json` is an unactuated MuJoCo smoke record, not a teacher policy or robot-ready rollout. Do not label browser kinematic exploration as a learned gait or Sim2Real result.

If the user changes the brief, create a new run. If they request a narrow change to an existing artifact, keep the source run and write a new version; do not overwrite evidence silently.
