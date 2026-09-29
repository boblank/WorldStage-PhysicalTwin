---
name: world-compose
description: Convert a valid WorldStage plan into a procedural 3D scene graph with bounded positions and explicit meter-scale coordinates.
---

# Compose scene geometry

Run `python3 studio/skill_cli.py compose --run-id <id>` after planning. Output: `runs/<id>/scene.json`. The browser renders known primitives with Three.js; these are generated design assets, not measured geometry or collision-certified meshes. Keep each object ID and plan reference stable so interaction and story stages can target it.
