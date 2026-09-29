---
name: nemotron-service-audit
description: Verify that a WorldStage run used an actual NVIDIA Nemotron checkpoint on the target GX10, with API, process, weight, and generated-object receipts.
---

# Nemotron service audit

Use this Skill before claiming NVIDIA model operation. On the target GX10, set `NEMOTRON_BASE_URL` and `NEMOTRON_MODEL` to the local OpenAI-compatible service and run `python3 studio/check_nemotron.py`. Its `API_PROBE_PASS_BACKEND_IDENTITY_PENDING` result proves only that the API returned a model ID and response.

Use `python3 studio/model_cli.py --help` for the complete inference CLI: `serve` launches a specified local llama-server and GGUF on loopback with file hashes, `stop` checks Linux process ownership, `doctor` checks `/models` and optional local hashes, `generate` creates one physical object with explicit model/template provenance, and `benchmark` evaluates three semantic object tasks. A failed model call returns a nonzero code unless `generate --allow-template` was explicitly requested. The benchmark requires actual Nemotron use and all six generated fields to be valid. On a client machine, reach GX10 via an SSH tunnel to the model port and pass its localhost URL to `--base-url`.

Complete the device proof by recording instance ID, hostname/architecture, GPU, the server process command, the actual checkpoint repository and revision, weight SHA256, inference backend version, `/v1/models`, and one new `/api/lab/object` result with `provenance.mode=nvidia_nemotron`. Preserve `model_candidate.json` and note every `model_fields_fallback` field. Never use a model alias alone as proof of checkpoint identity. Keep credentials out of receipts.

The included `examples/gx10-nemotron/receipt.json` shows the expected output shape. It proves Nemotron 3 Nano 4B GGUF ran on GX10 instance `53340625`; it does not prove Omni, Isaac Sim, physical parameter truth, or robot locomotion.
