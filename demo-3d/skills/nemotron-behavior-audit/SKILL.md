---
name: nemotron-behavior-audit
description: Review a recorded WorldStage exploration episode with NVIDIA Nemotron for evidence-linked scene risks and next experiments, while preserving deterministic physics gates.
---

# Nemotron behavior audit

Run `/lab.html` → `审核当前探索`, or call `POST /api/lab/episode-audit` with `{scenario, trajectory, mode}`. The server computes fixed trajectory metrics and calls `scene-readiness-gate` before sending a compact evidence summary to the configured Nemotron text model. The model may select supported risk codes and propose one robot task and next probe. Its review is advisory: it cannot make `sim2sim_ready` or `sim2real_ready` true or clear a scene gate failure.

The model receives structured text, not a screenshot or a WorldGen mesh. The attached Workshop uses TAO image grounding, TAO referring expressions, and a separate Qwen vision model. Those visual Skills are a possible future perception stage; do not attribute their outputs to Nemotron 4B. Run `python3 studio/behavior_benchmark.py --live` only with an actual Nemotron service, and report `NOT_RUN` if absent.
