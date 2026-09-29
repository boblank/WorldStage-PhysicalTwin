"""Local NVIDIA Nemotron lifecycle, generation, and task benchmark CLI.

Commands keep template fallback explicit and never expose the server publicly.
Run from demo-3d or pass absolute paths. Receipts are written under runs/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pipeline import ROOT, _write
from robot_world import generate_object

DEFAULT_MODEL = os.getenv('NEMOTRON_MODEL', 'nemotron-3-nano-4b-gguf')
DEFAULT_URL = os.getenv('NEMOTRON_BASE_URL', 'http://127.0.0.1:8000/v1')
STATE = ROOT / 'runs/nemotron-server.json'


def local_url(value: str) -> str:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'} or not parsed.port:
        raise ValueError('Nemotron endpoint must be an explicit local http URL (use an SSH tunnel for GX10)')
    return value.rstrip('/')


def api(base: str, route: str, body: dict | None = None, timeout: int = 45) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(base + route, data=data, headers={'Content-Type': 'application/json'}, method='POST' if data else 'GET')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def receipt(kind: str, payload: dict) -> Path:
    now = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    target = ROOT / 'runs' / f'nemotron-{kind}-{now}.json'
    _write(target, payload)
    return target


def doctor(args: argparse.Namespace) -> int:
    base = local_url(args.base_url)
    models = api(base, '/models')
    ids = [entry.get('id') for entry in models.get('data', []) if isinstance(entry, dict)]
    if 'nemotron' not in args.model.lower() or args.model not in ids:
        raise ValueError(f'Nemotron model {args.model!r} absent from /models: {ids}')
    result = {'schema': 'worldstage.nemotron_doctor.v1', 'status': 'API_READY_BACKEND_PROVENANCE_UNVERIFIED', 'base_url': base,
              'model': args.model, 'models_returned': ids, 'weight_sha256': None, 'binary_sha256': None}
    for name in ('weight', 'binary'):
        value = getattr(args, name)
        if value:
            path = Path(value).expanduser().resolve(strict=True)
            digest = sha_file(path)
            expected = getattr(args, f'expected_{name}_sha256')
            if expected and digest != expected.lower():
                raise ValueError(f'{name} SHA-256 mismatch: {digest}')
            result[f'{name}_sha256'] = digest
            result[f'{name}_path'] = str(path)
    if result['weight_sha256'] and result['binary_sha256']:
        result['status'] = 'API_READY_LOCAL_FILES_HASHED_PROCESS_OWNERSHIP_SEPARATE'
    target = receipt('doctor', result)
    print(json.dumps({'receipt': str(target), **result}, ensure_ascii=False, indent=2))
    return 0


def serve(args: argparse.Namespace) -> int:
    if STATE.exists():
        raise ValueError(f'Existing state file: {STATE}; use stop or inspect it before starting another server')
    binary = Path(args.binary).expanduser().resolve(strict=True)
    weight = Path(args.weight).expanduser().resolve(strict=True)
    if not binary.is_file() or not os.access(binary, os.X_OK) or not weight.is_file():
        raise ValueError('Binary must be executable and weight must be a file')
    weight_sha, binary_sha = sha_file(weight), sha_file(binary)
    if args.expected_weight_sha256 and weight_sha != args.expected_weight_sha256.lower():
        raise ValueError('Weight SHA-256 mismatch')
    if args.expected_binary_sha256 and binary_sha != args.expected_binary_sha256.lower():
        raise ValueError('Binary SHA-256 mismatch')
    if 'nemotron' not in args.model.lower():
        raise ValueError('Core model alias must identify Nemotron')
    command = [str(binary), '-m', str(weight), '--alias', args.model, '--host', '127.0.0.1', '--port', str(args.port), '-ngl', str(args.gpu_layers), '-c', str(args.context), '--jinja']
    STATE.parent.mkdir(parents=True, exist_ok=True)
    log = ROOT / 'runs/nemotron-server.log'
    with log.open('ab') as output:
        process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    state = {'schema': 'worldstage.nemotron_server.v1', 'pid': process.pid, 'command': command, 'binary_sha256': binary_sha,
             'weight_sha256': weight_sha, 'model': args.model, 'base_url': f'http://127.0.0.1:{args.port}/v1', 'log': str(log)}
    _write(STATE, state)
    deadline = time.monotonic() + args.wait_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(json.dumps({'status': 'START_FAILED', 'state': str(STATE), 'log': str(log)}))
            return 1
        try:
            models = api(state['base_url'], '/models', timeout=2)
            if args.model in [entry.get('id') for entry in models.get('data', [])]:
                print(json.dumps({'status': 'READY', 'state': str(STATE), 'pid': process.pid, 'model': args.model}))
                return 0
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
        time.sleep(1)
    print(json.dumps({'status': 'STARTED_NOT_READY', 'state': str(STATE), 'pid': process.pid, 'log': str(log)}))
    return 2


def stop(_args: argparse.Namespace) -> int:
    state = json.loads(STATE.read_text())
    pid = int(state['pid'])
    # Only stop the process launched by this CLI, with its exact command and executable.
    proc = Path(f'/proc/{pid}/cmdline')
    if not proc.is_file():
        raise ValueError('Process ownership cannot be checked on this host; stop manually')
    actual = [entry.decode() for entry in proc.read_bytes().split(b'\0') if entry]
    if actual != state['command'] or sha_file(Path(actual[0])) != state['binary_sha256']:
        raise ValueError('Process identity differs from saved state; refusing to stop')
    os.kill(pid, signal.SIGTERM)
    STATE.unlink()
    print(json.dumps({'status': 'SIGTERM_SENT', 'pid': pid}))
    return 0


def generate(args: argparse.Namespace) -> int:
    os.environ['NEMOTRON_BASE_URL'] = local_url(args.base_url)
    os.environ['NEMOTRON_MODEL'] = args.model
    result = generate_object(args.prompt, allow_model=True)
    model_used = result['provenance']['mode'] == 'nvidia_nemotron'
    if not model_used and not args.allow_template:
        result['status'] = 'FAIL_MODEL_NOT_USED'
    else:
        result['status'] = 'PASS_MODEL' if model_used else 'PASS_EXPLICIT_TEMPLATE'
    target = receipt('generate', result)
    print(json.dumps({'receipt': str(target), **result}, ensure_ascii=False, indent=2))
    return 0 if model_used or args.allow_template else 1


def benchmark(args: argparse.Namespace) -> int:
    os.environ['NEMOTRON_BASE_URL'] = local_url(args.base_url)
    os.environ['NEMOTRON_MODEL'] = args.model
    cases = [
        ('为 S10 设计一段固定的低摩擦斜坡，帮助测试攀爬。', 'ramp'),
        ('创建一个可滚动的金属球，测试碰撞与避障。', 'sphere'),
        ('创建一根固定的石柱，测试绕行。', 'pillar'),
    ]
    rows = []
    for prompt, expected in cases:
        start = time.monotonic()
        result = generate_object(prompt, allow_model=True)
        provenance = result['provenance']
        rows.append({'prompt': prompt, 'expected_kind': expected, 'actual_kind': result['object']['kind'],
                     'model_used': provenance['mode'] == 'nvidia_nemotron', 'all_fields_model_accepted': len(provenance['model_fields_fallback']) == 0,
                     'semantic_match': result['object']['kind'] == expected, 'latency_ms': round((time.monotonic() - start) * 1000),
                     'run_id': result['run_id'], 'candidate_sha256': provenance.get('model_candidate_sha256')})
    success = sum(row['model_used'] and row['all_fields_model_accepted'] and row['semantic_match'] for row in rows)
    report = {'schema': 'worldstage.nemotron_benchmark.v1', 'scope': 'three_object_generation_cases_not_robot_training',
              'model': args.model, 'base_url': args.base_url, 'cases': rows, 'strict_success': success,
              'total': len(rows), 'status': 'PASS' if success == len(rows) else 'FAIL', 'template_fallback_count': sum(not row['model_used'] for row in rows)}
    target = receipt('benchmark', report)
    print(json.dumps({'receipt': str(target), **report}, ensure_ascii=False, indent=2))
    return 0 if success == len(rows) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('doctor', 'generate', 'benchmark'):
        item = sub.add_parser(name)
        item.add_argument('--base-url', default=DEFAULT_URL)
        item.add_argument('--model', default=DEFAULT_MODEL)
    doc = sub.choices['doctor']
    for name in ('weight', 'binary'):
        doc.add_argument(f'--{name}')
        doc.add_argument(f'--expected-{name}-sha256')
    gen = sub.choices['generate']
    gen.add_argument('prompt')
    gen.add_argument('--allow-template', action='store_true')
    item = sub.add_parser('serve')
    item.add_argument('--binary', required=True)
    item.add_argument('--weight', required=True)
    item.add_argument('--model', default=DEFAULT_MODEL)
    item.add_argument('--port', type=int, default=8000)
    item.add_argument('--gpu-layers', type=int, default=99)
    item.add_argument('--context', type=int, default=4096)
    item.add_argument('--wait-seconds', type=int, default=60)
    item.add_argument('--expected-weight-sha256')
    item.add_argument('--expected-binary-sha256')
    sub.add_parser('stop')
    args = parser.parse_args()
    try:
        return {'doctor': doctor, 'serve': serve, 'stop': stop, 'generate': generate, 'benchmark': benchmark}[args.command](args)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, urllib.error.URLError, TimeoutError) as exc:
        print(f'ERROR: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
