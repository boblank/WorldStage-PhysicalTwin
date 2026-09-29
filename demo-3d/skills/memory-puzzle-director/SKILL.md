---
name: memory-puzzle-director
description: Guide the My Robot Avatar portal story through avatar choice, exploration, object generation, scene qualification, and branching evidence-based endings.
---

# Memory puzzle director

Open `/lab.html` and present the portal welcome before any world action. Lead the user through four clues in order: confirm an avatar URDF; reach the visible anchor near `(-8, -5)` with the browser proxy; create a new object with explicit Nemotron or template provenance; run the scene readiness gate. The app records clue state and the selected ending in exported trajectory JSON.

Offer three possible truths after the four clues: laboratory test world, remembered real place, or digital robot twin. Each ending states what evidence would settle it. The narrative choices are fictional; physical claims still require measured parameters, same-scene simulator runs, and authorized real robot feedback. A WorldGen image or scene counts as a real-world source only with its original export, permission, SHA, scale, and collision provenance.
