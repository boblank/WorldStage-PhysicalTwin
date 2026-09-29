---
name: world-intake
description: Turn a user's interactive 3D scene brief into a bounded, attributed intake artifact. Use before scene planning when a new text brief arrives.
---

# Intake the brief

Run `python3 studio/skill_cli.py intake --run-id <id> --prompt '<brief>'` from `demo-3d/`. Output is `runs/<id>/intake.json` with the original user text, source type, status, and UTC time. Do not add factual claims to the brief. The current demo accepts text only; image-to-3D and real-world geometry capture are future adapters.
