---
name: world-interact
description: Add clickable, reversible interactions to WorldStage scene objects when the user wants a playable scene rather than a static model.
---

# Design interactions

Run `python3 studio/skill_cli.py interact --run-id <id>` after scene composition. Output: `runs/<id>/interactions.json`. Every event must reference an existing scene object and declare a visible, reversible effect. The demo currently supports `click → awaken_and_reveal`; do not claim arbitrary gameplay or physics scripting.
