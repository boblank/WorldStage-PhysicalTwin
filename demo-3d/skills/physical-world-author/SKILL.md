---
name: physical-world-author
description: Create a new geometry-and-physics object inside WorldStage from a user prompt, with a strict object schema and NVIDIA Nemotron or explicit template provenance.
---

# Physical world author

Use `POST /api/lab/object` with `prompt` and optional `mode=template`; the same path is called from `/lab.html`. Core planning uses NVIDIA Nemotron configured by `NEMOTRON_BASE_URL` and `NEMOTRON_MODEL`. Accept only supported shape, metric size, mass, friction, material, and a short name. `studio/robot_world.py:generate_object` records a run under `runs/lab-*/`. Inspect `generated_object.json` before claiming model inference. New objects can be static or dynamic and are added to Rapier with gravity and contact. Template runs must remain labeled `template`.
