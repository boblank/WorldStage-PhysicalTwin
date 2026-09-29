"""Read-only Nemotron API probe; backend identity still needs GX10 process/weight evidence."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.getenv('NEMOTRON_BASE_URL', '').rstrip('/')
MODEL = os.getenv('NEMOTRON_MODEL', '')


def get_json(path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, headers={'Content-Type': 'application/json'}, method='POST' if data else 'GET')
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def main() -> int:
    if not BASE or 'nemotron' not in MODEL.lower():
        print('NOT_RUN: set NEMOTRON_BASE_URL and a Nemotron NEMOTRON_MODEL', file=sys.stderr)
        return 2
    if not BASE.startswith(('http://127.0.0.1:', 'http://localhost:')):
        print('NOT_RUN: this probe only accepts a local forwarded endpoint', file=sys.stderr)
        return 2
    try:
        models = get_json('/models')
        ids = [item.get('id') for item in models.get('data', []) if isinstance(item, dict)]
        if MODEL not in ids:
            raise ValueError(f'configured model absent from /models: {ids}')
        prompt = '给 S10 四足机器人设计一个新的雨后斜坡障碍。只输出 JSON，包含 name、kind、size、mass_kg、friction、material。'
        started = time.monotonic()
        result = get_json('/chat/completions', {'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'temperature': 0.1, 'max_tokens': 300})
        latency_ms = round((time.monotonic() - started) * 1000)
        content = result['choices'][0]['message']['content']
        if not content:
            raise ValueError('empty completion')
        receipt = {'status': 'API_PROBE_PASS_BACKEND_IDENTITY_PENDING', 'model_requested': MODEL, 'models_returned': ids, 'response_model': result.get('model'), 'latency_ms': latency_ms, 'prompt': prompt, 'content': content, 'host': platform.node(), 'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'backend_identity_required': ['GX10 instance identity', 'server process/container', 'weight or config SHA']}
        path = ROOT / 'runs' / f'nemotron-api-probe-{time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        blob = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode()
        path.write_bytes(blob)
        print(f'{receipt["status"]}: {path} sha256={hashlib.sha256(blob).hexdigest()}')
        return 0
    except Exception as exc:
        print(f'NOT_RUN: {type(exc).__name__}: {str(exc)[:180]}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
