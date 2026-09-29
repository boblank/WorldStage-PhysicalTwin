---
name: physics-scenario-export
description: Convert a metric WorldStage physical scenario into a standalone MuJoCo XML world for paired physics runs and review.
---

# Physics scenario export

Run `python3 studio/robot_world.py` or call `POST /api/lab/mjcf` with `worldstage.physical.v1` JSON. The scene records z-up meters, gravity `[0,0,-9.81]`, box/sphere geometry, mass, friction, and static/dynamic state. Export `world.xml`, then load and step it in MuJoCo before claiming simulator compatibility. The XML is an environment file: it does not embed the S10 controller, sensors, or actuator model. Align those separately before sim2sim scoring. Use fixed initial state and record first differences in pose, contact, and event time.
