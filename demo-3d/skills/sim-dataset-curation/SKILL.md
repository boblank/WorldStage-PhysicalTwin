---
name: sim-dataset-curation
description: Convert audited game navigation traces into source-linked simulator task candidates without mislabeling proxy motion as robot policy training data.
---

# Sim dataset curation

Use the audit panel's `训练候选数据 .json` or the archived `candidate.json` under `runs/episode-*`. Keep each transition's position, next position, direction intent, human/scripted source, and proxy contact delta. Retain scene and trajectory SHA-256, URDF SHA-256, WorldGen provenance, and puzzle events. `usage=scenario_selection_and_goal_inference_only` is the current admissible use.

Reject malformed or non-monotonic traces. Treat command-without-progress windows and contact hotspots as candidates for new replay tasks, not validated failure labels. Before policy learning or Sim2Real claims, calibrate scale and contact, replay the same task with an actuated URDF in two engines, check failure distributions, and add authorized real robot measurements. The current `policy_training_ready`, `sim2sim_ready`, and `sim2real_ready` fields remain false.
