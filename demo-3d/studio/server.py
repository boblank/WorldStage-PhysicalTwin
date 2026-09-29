"""Minimal same-origin server for the WorldStage demo."""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from pipeline import ROOT, RUNS, build
from robot_world import base_scenario, generate_object, scenario_mjcf
from scene_gate import qualify


DIST = ROOT / "dist"


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, value: object) -> None:
        data = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/api/health":
            model = os.getenv("NEMOTRON_MODEL", "")
            base = os.getenv("NEMOTRON_BASE_URL", "").rstrip("/")
            configured = bool(base and "nemotron" in model.lower())
            connected = False
            if configured:
                try:
                    with urllib.request.urlopen(base + "/models", timeout=2) as response:
                        ids = [item.get("id") for item in json.load(response).get("data", [])]
                    connected = model in ids
                except Exception:
                    pass
            self._json(200, {"status": "ok", "model_configured": configured, "model_connected": connected, "model_id": model if connected else None, "model_provider": "NVIDIA Nemotron", "dist_exists": DIST.is_dir()})
            return
        if path == "/api/lab/scenario":
            self._json(200, base_scenario())
            return
        if path == "/api/lab/physics-evidence":
            evidence = ROOT / "examples/physical-world/sim2sim_drop_compare.json"
            if not evidence.is_file():
                self._json(404, {"error": "physics_evidence_not_run"}); return
            self._json(200, json.loads(evidence.read_text())); return
        if path.startswith("/api/runs/"):
            name = path.removeprefix("/api/runs/")
            if "/" in name or ".." in name:
                self._json(400, {"error": "invalid_run_id"}); return
            manifest = RUNS / name / "manifest.json"
            if not manifest.is_file():
                self._json(404, {"error": "run_not_found"}); return
            self._json(200, json.loads(manifest.read_text())); return
        file = (DIST / (path.lstrip("/") or "index.html")).resolve()
        if not file.is_relative_to(DIST.resolve()) or not file.is_file():
            self._json(404, {"error": "not_found"}); return
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in ("/api/build", "/api/lab/object", "/api/lab/mjcf", "/api/lab/scene-gate"):
            self._json(404, {"error": "not_found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536:
                self._json(413, {"error": "body_size_invalid"}); return
            payload = json.loads(self.rfile.read(length))
            if self.path == "/api/lab/scene-gate":
                report = qualify(payload)
                self._json(200 if report["structural_status"] == "PASS" else 422, report)
                return
            if self.path == "/api/lab/mjcf":
                self._json(200, {"xml": scenario_mjcf(payload)})
                return
            prompt = payload.get("prompt", "")
            if not isinstance(prompt, str) or not prompt.strip():
                self._json(400, {"error": "prompt_required"}); return
            result = (build(prompt, allow_model=payload.get("mode") != "template")
                      if self.path == "/api/build" else
                      generate_object(prompt, allow_model=payload.get("mode") != "template"))
            self._json(200, result)
        except Exception as exc:
            self._json(500, {"error": "build_failed", "detail": str(exc)[:200]})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8765"))
    print(f"WorldStage http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer((os.getenv("HOST", "127.0.0.1"), port), Handler).serve_forever()
