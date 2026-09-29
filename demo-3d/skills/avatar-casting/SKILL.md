---
name: avatar-casting
description: Select a real open-source URDF as the user's robot avatar and report its source, collision geometry, mass, and browser-motion limits.
---

# Avatar casting

Use `/lab.html` to choose DEEPRobotics S10 or ROBOTIS TurtleBot3 Burger. The files in `public/robots/` retain each original URDF, a mesh-free collision derivative, source SHA, repository revision, and license. `studio/import_s10.py` and `studio/import_turtlebot3.py` regenerate the derivatives. Confirm the chosen avatar before exploration; export its source SHA with the trajectory.

S10 and TurtleBot3 use different browser collision proxies and speeds. Both are kinematic previews; do not infer actuator torque, slope climbing, turning limits, or true gait. The TurtleBot3 collision URDF compiled in MuJoCo, but no driven mission test was performed. A photograph is not a robot-ready URDF: require a 3D mesh, scale, joint tree, inertia, collision proxies, actuation limits, and simulator validation before admitting an image-derived avatar.
