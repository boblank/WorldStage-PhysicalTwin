---
name: behavior-benchmark
description: Evaluate WorldStage episode capture, scene-risk detection, and simulator-candidate boundaries with frozen positive and negative cases; optionally test live Nemotron review quality.
---

# Behavior benchmark

From `demo-3d/`, run `python3 studio/behavior_benchmark.py` for the frozen browser traces, a real 18-to-19-object scene split, and synthetic negative cases. The report tests recorded contacts, commanded-but-stuck detection, human control provenance, invalid time rejection, and scene gate precedence. It does not contact a model.

With `NEMOTRON_BASE_URL` and `NEMOTRON_MODEL` set to a live NVIDIA service, run `python3 studio/behavior_benchmark.py --live --output examples/skill-benchmark/behavior_model_report.json`. This checks that the model gives a next probe and handles a stuck trace versus a progressing trace without unsupported risks. Keep model quality, offline Skill contracts, dual-engine robot replay, and real robot transfer as separate result fields.
