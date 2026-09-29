---
name: behavior-episode-capture
description: Capture a WorldStage game exploration episode with command provenance, robot identity, contacts, and puzzle events for later scene analysis.
---

# Behavior episode capture

In `/lab.html`, record each 0.1-second browser frame with root position, direction intent, cumulative proxy contacts, and `control_source` (`keyboard`, `clicked_goal`, `scripted_patrol`, or `idle`). Record human click goals and puzzle events separately. Download `worldstage-proxy-trajectory.json` or use the behavior audit panel to archive a scene and episode together.

Keep the `source_urdf_sha256` and WorldGen source receipt. The browser avatar is a kinematic collision proxy; clicked goals and scripted patrols are not joint commands or human robot demonstrations. Use `python3 studio/behavior_benchmark.py` to check the episode contract and negative cases.
