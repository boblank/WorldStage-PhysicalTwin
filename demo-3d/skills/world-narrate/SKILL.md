---
name: world-narrate
description: Write short, object-linked narrative beats for a WorldStage scene so a visitor discovers a story by interacting with its 3D objects.
---

# Link story to objects

Run `python3 studio/skill_cli.py narrate --run-id <id>` after scene composition. Output: `runs/<id>/story.json`. Each beat references exactly one scene object. In template mode, the text is predetermined placeholder content and should be labeled as such; local model mode can create theme-specific text but still needs the verifier.
