---
name: worldgen-visual-intake
description: Import an authorized Hyper3D WorldGen scene export as a traceable visual layer while keeping scale, collision, and robot traversability unverified.
---

# WorldGen visual intake

Read `public/worldgen/manifest.json`. It identifies the original source image SHA, exported ZIP SHA, seven shaded GLB files, each file SHA and transform matrix. `/lab.html` loads all seven actual GLBs with `GLTFLoader` and labels the visual layer. The displayed scale and offset are presentation choices, not measured meters. Keep the original export in `worldgen-assets/` outside the runtime package.

Before treating any object as physical, obtain a metric scale reference, coordinate-frame mapping, collision mesh or proxy, supported surface contacts, and measured or bounded mass/friction. Run `scene-readiness-gate`, then an actual target-simulator compile and step. Current imported WorldGen assets are visual-only; the Rapier obstacle world is a separate authored collision scene. Do not say that WorldGen geometry is already traversable by S10 or TurtleBot3.
