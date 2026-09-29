---
name: world-plan
description: Convert an attributed WorldStage brief into a bounded interactive scene plan with title, palette, six objects, and explicit model or template provenance.
---

# Plan the world

After intake, run `python3 studio/skill_cli.py plan --run-id <id>` from `demo-3d/`. Set `NEMOTRON_BASE_URL` and `NEMOTRON_MODEL` to use NVIDIA Nemotron through a local OpenAI-compatible endpoint. For an explicitly non-AI demo, add `--template`. The planner accepts only known primitive object types and valid colors, limits text lengths, and records fallback reason. Inspect `runs/<id>/plan.json` before describing the result. A plan is a creative proposal, not a reconstruction of a real location.
