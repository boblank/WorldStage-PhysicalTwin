---
name: worldgen-visual-intake
description: Import an authorized Hyper3D WorldGen export with source-hashed visual meshes and reviewable static Rapier mesh contact, while keeping metric scale and robot traversability unverified.
---

# WorldGen visual intake

Read `public/worldgen/manifest.json`. It identifies the original source image SHA, exported ZIP SHA, seven PBR GLB files, each file SHA and transform matrix. `/lab.html` loads the actual GLBs with `GLTFLoader`, then builds fixed Rapier triangle-mesh colliders from their transformed vertices and indices. The one-source-unit-to-one-demo-metre convention is a design assumption, not a measured scale. Keep the original export in `worldgen-assets/` outside the runtime package.

Before robot training, obtain a measured metric reference, validate contact behaviour against a known body, and measure or bound mass/friction. Run `scene-readiness-gate`, then an actual target-simulator compile and step. The browser can collide against exported static triangles, but MJCF still exports primitive proxies. The gate must report this cross-engine shape mismatch and block robot training. Do not claim calibrated contact, S10/TurtleBot3 traversability, or Sim2Real data from browser proxy exploration.
