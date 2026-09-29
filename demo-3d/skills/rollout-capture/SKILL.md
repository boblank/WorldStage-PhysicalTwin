---
name: rollout-capture
description: Record a WorldStage robot proxy exploration trace and distinguish preview evidence from joint-level simulator or real-robot data.
---

# Rollout capture

Open `/lab.html`, move the S10 collision proxy using W/A/S/D, a clicked ground target, or automatic exploration, then download `worldstage-proxy-trajectory.json`. The trace includes sample time, root position, cumulative proxy contact count, scenario gravity, URDF SHA, and `robot_control=kinematic_collision_proxy`. Verify its source before reuse. It can identify promising generated obstacle layouts; it contains no joint torques, wheel/leg commands, contact impulses, or validated success labels. For robot learning, replay a frozen scenario in MuJoCo/Isaac Sim and gather real measurements under separate authorization.
