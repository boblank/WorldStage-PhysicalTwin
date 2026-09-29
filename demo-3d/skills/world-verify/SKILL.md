---
name: world-verify
description: Check WorldStage scene, interaction, and story artifacts before a playable demo is shared or exported.
---

# Verify the deliverable contract

Run `python3 studio/skill_cli.py verify --run-id <id>` after `compose`, `interact`, and `narrate`. Output: `runs/<id>/evaluation.json`. Require six unique object IDs, complete interaction and story targets, and bounded positions. `PASS` means only these four structural checks passed. It does not prove aesthetic quality, factual grounding, GPU inference, or user acceptance.
