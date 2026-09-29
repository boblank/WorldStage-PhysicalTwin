---
name: robot-urdf-import
description: Inspect and package a real robot URDF for browser visualization and downstream simulation contracts; use when a robot model, links, joints, inertias, or collision shapes are needed.
---

# Robot URDF import

Run `python3 studio/import_s10.py` from this project. It reads the existing DEEPRobotics S10 URDF in the user workspace without modifying it, retains the original SHA-256 and BSD-3-Clause license, and writes the original URDF, a collision-only URDF, and `S10-collision.json` under `public/robots/`. Verify 20 links, 19 joints, 27 primitive colliders, and approximately 18.987425 kg summed URDF mass. The browser visualizes the collision tree only. Preserve the original file for reproducibility. Do not describe a kinematic browser preview as S10 motor dynamics or robot execution.
