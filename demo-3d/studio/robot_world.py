"""Generated physical-world scenarios, Nemotron object planning, and MuJoCo export."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pipeline import ROOT, RUNS, _write

KIND = {'box', 'pillar', 'ramp', 'sphere', 'tree', 'crystal', 'building'}
PALETTES = {'stone': '#9faab0', 'metal': '#81b5c1', 'wood': '#b9956a', 'grass': '#7fae8a', 'warning': '#d8a56b'}


def base_scenario() -> dict[str, Any]:
    robot_sha = json.loads((ROOT / 'public/robots/S10-collision.json').read_text())['source_sha256']
    obstacles = [
        {'id': 'step-a', 'name': '低台阶', 'kind': 'box', 'position': [-5.0, 0.0, 0.12], 'size': [3.0, 2.0, 0.24], 'yaw': 0, 'mass_kg': 0, 'friction': 0.85, 'material': 'stone'},
        {'id': 'step-b', 'name': '中台阶', 'kind': 'box', 'position': [-1.5, 0.0, 0.22], 'size': [3.0, 2.0, 0.44], 'yaw': 0, 'mass_kg': 0, 'friction': 0.85, 'material': 'stone'},
        {'id': 'platform', 'name': '高台', 'kind': 'box', 'position': [2.5, 0.0, 0.35], 'size': [4.0, 3.0, 0.7], 'yaw': 0, 'mass_kg': 0, 'friction': 0.8, 'material': 'metal'},
        {'id': 'ramp', 'name': '斜坡', 'kind': 'ramp', 'position': [8.0, 0.0, 0.27], 'size': [4.0, 2.5, 0.16], 'yaw': -0.15, 'mass_kg': 0, 'friction': 0.65, 'material': 'wood'},
        {'id': 'test-cube', 'name': '重力测试箱', 'kind': 'box', 'position': [0.0, -6.0, 3.0], 'size': [0.6, 0.6, 0.6], 'yaw': 0, 'mass_kg': 2.0, 'friction': 0.65, 'material': 'warning'},
        {'id': 'wet-yard', 'name': '雨后低摩擦试验区', 'kind': 'box', 'position': [-22.0, -8.0, 0.025], 'size': [12.0, 8.0, 0.05], 'yaw': 0, 'mass_kg': 0, 'friction': 0.25, 'material': 'metal'},
        {'id': 'rough-lane', 'name': '高摩擦粗糙带', 'kind': 'box', 'position': [20.0, -6.0, 0.025], 'size': [16.0, 5.0, 0.05], 'yaw': 0, 'mass_kg': 0, 'friction': 1.15, 'material': 'stone'},
        {'id': 'wood-yard', 'name': '木质操作平台', 'kind': 'box', 'position': [18.0, 16.0, 0.025], 'size': [12.0, 10.0, 0.05], 'yaw': 0, 'mass_kg': 0, 'friction': 0.55, 'material': 'wood'},
    ]
    return {'schema': 'worldstage.physical.v1', 'seed': 290929, 'units': 'm_kg_s', 'coordinate_system': 'z_up', 'gravity_m_s2': [0, 0, -9.81], 'parameter_status': 'design_assumption_unmeasured', 'visual_generation': 'procedural_geometry_and_canvas_material', 'ground': {'size_m': [80, 80], 'friction': 0.8}, 'robot': {'name': 'DEEPRobotics S10', 'asset': 'robots/S10-collision.urdf', 'source_urdf_sha256': robot_sha, 'browser_mode': 'kinematic_collision_proxy_only'}, 'obstacles': obstacles}


def _fallback(prompt: str) -> dict[str, Any]:
    q = prompt.lower()
    if any(x in q for x in ('球', '滚', 'sphere', 'ball')):
        kind, size, mass, material = 'sphere', [0.6, 0.6, 0.6], 1.2, 'metal'
    elif any(x in q for x in ('树', '森林', 'tree', 'forest')):
        kind, size, mass, material = 'tree', [1.8, 1.8, 3.2], 0, 'grass'
    elif any(x in q for x in ('水晶', '晶体', 'crystal')):
        kind, size, mass, material = 'crystal', [0.8, 0.8, 1.7], 0, 'metal'
    elif any(x in q for x in ('建筑', '房子', 'building', 'house')):
        kind, size, mass, material = 'building', [2.2, 2.2, 2.4], 0, 'stone'
    elif any(x in q for x in ('坡', 'ramp', 'slope')):
        kind, size, mass, material = 'ramp', [3.0, 2.0, 0.18], 0, 'wood'
    elif any(x in q for x in ('塔', '柱', 'pillar', 'tower')):
        kind, size, mass, material = 'pillar', [0.8, 0.8, 2.2], 0, 'stone'
    else:
        kind, size, mass, material = 'box', [1.2, 1.2, 0.7], 0, 'stone'
    return {'name': prompt.strip()[:24] or '新障碍', 'kind': kind, 'size': size, 'mass_kg': mass, 'friction': 0.8, 'material': material}


def _nemotron(prompt: str) -> tuple[dict[str, Any] | None, str | None]:
    base, model = os.getenv('NEMOTRON_BASE_URL', '').rstrip('/'), os.getenv('NEMOTRON_MODEL', '')
    if not base or not model:
        return None, 'NVIDIA Nemotron 服务未配置'
    if 'nemotron' not in model.lower():
        return None, '核心模型必须为 NVIDIA Nemotron'
    system = ('You design robot simulation obstacles. Output only one JSON object with: name (24 characters max), '
              'kind (box/pillar/ramp/sphere/tree/crystal/building), size ([length,width,height] in meters, each 0.2 to 4), '
              'mass_kg (0 means fixed; dynamic 0.1 to 10), friction (0.2 to 1.5), '
              'material (stone/metal/wood/grass/warning). Use a physical object suitable for robot testing. '
              'The user request may be in Chinese; understand it and keep the output schema in English.')
    body = json.dumps({'model': model, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}], 'max_tokens': 500, 'temperature': 0.25}).encode()
    request = urllib.request.Request(f'{base}/chat/completions', data=body, headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            payload = json.load(response)
        content = payload['choices'][0]['message']['content']
        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        match = re.search(r'\{.*\}', content, re.S)
        if not match:
            raise ValueError('no JSON object')
        return json.loads(match.group(0)), None
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, f'Nemotron 调用失败：{type(exc).__name__}'


def generate_object(prompt: str, allow_model: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    fallback = _fallback(prompt)
    candidate, error = _nemotron(prompt) if allow_model else (None, '用户选择模板模式')
    raw = candidate if isinstance(candidate, dict) else {}
    accepted = {
        'name': isinstance(raw.get('name'), str) and bool(raw['name'].strip()),
        'kind': raw.get('kind') in KIND,
        'size': isinstance(raw.get('size'), list) and len(raw['size']) == 3 and all(isinstance(v, (float, int)) and 0.2 <= v <= 4 for v in raw['size']),
        'mass_kg': isinstance(raw.get('mass_kg'), (float, int)) and (raw['mass_kg'] == 0 or 0.1 <= raw['mass_kg'] <= 10),
        'friction': isinstance(raw.get('friction'), (float, int)) and 0.2 <= raw['friction'] <= 1.5,
        'material': raw.get('material') in PALETTES,
    }
    kind = raw.get('kind') if raw.get('kind') in KIND else fallback['kind']
    size = raw.get('size')
    if not (isinstance(size, list) and len(size) == 3 and all(isinstance(v, (float, int)) and 0.2 <= v <= 4 for v in size)):
        size = fallback['size']
    mass = raw.get('mass_kg')
    if not isinstance(mass, (float, int)) or not (mass == 0 or 0.1 <= mass <= 10):
        mass = fallback['mass_kg']
    if kind in ('ramp', 'tree', 'building', 'pillar') and mass > 0:
        mass = 0
        accepted['mass_kg'] = False
    friction = raw.get('friction')
    if not isinstance(friction, (float, int)) or not 0.2 <= friction <= 1.5:
        friction = fallback['friction']
    material = raw.get('material') if raw.get('material') in PALETTES else fallback['material']
    name = raw.get('name') if isinstance(raw.get('name'), str) else fallback['name']
    name = name.strip()[:24] or fallback['name']
    now = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    ident = hashlib.sha256(f'{now}:{prompt}:{os.urandom(8).hex()}'.encode()).hexdigest()[:8]
    obj = {'id': f'generated-{ident}', 'name': name, 'kind': kind, 'size': size, 'position': [0, 0, size[2] / 2 if mass == 0 else 3], 'yaw': -0.15 if kind == 'ramp' else 0, 'mass_kg': mass, 'friction': friction, 'material': material, 'physical_parameter_status': 'unmeasured_hypothesis'}
    provenance = {'mode': 'nvidia_nemotron' if candidate else 'template', 'model': os.getenv('NEMOTRON_MODEL') if candidate else None, 'fallback_reason': error, 'prompt': prompt, 'server_generation_ms': round((time.monotonic() - started) * 1000), 'model_fields_accepted': [key for key, ok in accepted.items() if ok] if candidate else [], 'model_fields_fallback': [key for key, ok in accepted.items() if not ok] if candidate else list(accepted)}
    folder = RUNS / f'lab-{now}-{ident}'
    if candidate:
        provenance['model_candidate_sha256'] = _write(folder / 'model_candidate.json', raw)
    digest = _write(folder / 'generated_object.json', {'object': obj, 'provenance': provenance})
    _write(folder / 'manifest.json', {'status': 'COMPLETE', 'sha256': digest, 'mode': provenance['mode']})
    return {'object': obj, 'provenance': provenance, 'run_id': folder.name}


def scenario_mjcf(scenario: dict[str, Any]) -> str:
    if scenario.get('coordinate_system') != 'z_up' or scenario.get('gravity_m_s2') != [0, 0, -9.81]:
        raise ValueError('unsupported coordinate/gravity contract')
    root = ET.Element('mujoco', model='worldstage_physical_world')
    ET.SubElement(root, 'compiler', angle='radian', coordinate='local')
    ET.SubElement(root, 'option', gravity='0 0 -9.81', timestep='0.005')
    world = ET.SubElement(root, 'worldbody')
    ET.SubElement(world, 'geom', name='ground', type='plane', size='40 40 0.1', friction=f"{scenario['ground']['friction']} 0.01 0.0001")
    for obj in scenario['obstacles']:
        if not isinstance(obj.get('id'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]+', obj['id']):
            raise ValueError('invalid obstacle id')
        kind = obj['kind']
        if kind not in KIND:
            raise ValueError('unsupported obstacle')
        x, y, z = obj['position']
        sx, sy, sz = obj['size']
        if any(not isinstance(v, (float, int)) or abs(v) > 40 for v in (x, y, z, sx, sy, sz)) or min(sx, sy, sz) <= 0:
            raise ValueError('invalid dimensions')
        body = ET.SubElement(world, 'body', name=obj['id'], pos=f'{x} {y} {z}', euler=f'0 {obj.get("yaw", 0)} 0')
        if obj['mass_kg'] > 0:
            ET.SubElement(body, 'freejoint')
        geom_type = 'sphere' if kind == 'sphere' else 'cylinder' if kind in ('pillar', 'tree') else 'box'
        geom_size = f'{sx / 2}' if kind == 'sphere' else f'{sx / 2} {sz / 2}' if kind in ('pillar', 'tree') else f'{sx / 2} {sy / 2} {sz / 2}'
        attrs = {'name': f"{obj['id']}-geom", 'type': geom_type, 'size': geom_size, 'friction': f"{obj['friction']} 0.01 0.0001"}
        if obj['mass_kg'] > 0:
            attrs['mass'] = str(obj['mass_kg'])
        ET.SubElement(body, 'geom', **attrs)
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='unicode') + '\n'


if __name__ == '__main__':
    scenario = base_scenario()
    folder = ROOT / 'examples' / 'physical-world'
    folder.mkdir(parents=True, exist_ok=True)
    _write(folder / 'scenario.json', scenario)
    (folder / 'world.xml').write_text(scenario_mjcf(scenario))
    print('wrote physical-world example')
