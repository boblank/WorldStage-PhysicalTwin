"""Verify a WorldStage source bundle and an example run without network access."""
from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from pipeline import ROOT, build, verify
from robot_world import generate_object
from scene_gate import qualify


def main() -> None:
    required = [ROOT / 'dist/index.html', ROOT / 'dist/lab.html', ROOT / 'package.json', ROOT / 'package-lock.json', ROOT / 'public/robots/S10-source.urdf', ROOT / 'public/robots/S10-collision.urdf', ROOT / 'public/robots/LICENSE-S10.txt', ROOT / 'examples/gx10-nemotron/receipt.json']
    assert all(path.is_file() for path in required), 'build files missing'
    skills = sorted((ROOT / 'skills').glob('*/SKILL.md'))
    assert len(skills) == 13, f'expected 13 skills, found {len(skills)}'
    robot = json.loads((ROOT / 'public/robots/S10-collision.json').read_text())
    assert len(robot['links']) == 20 and len(robot['joints']) == 19
    assert hashlib.sha256((ROOT / 'public/robots/S10-source.urdf').read_bytes()).hexdigest() == robot['source_sha256']
    scenario = json.loads((ROOT / 'examples/physical-world/scenario.json').read_text())
    assert scenario['ground']['size_m'] == [80, 80] and scenario['gravity_m_s2'] == [0, 0, -9.81]
    assert len(scenario['obstacles']) >= 8 and min(o['friction'] for o in scenario['obstacles']) <= 0.25 and max(o['friction'] for o in scenario['obstacles']) >= 1.15
    assert ET.parse(ROOT / 'examples/physical-world/world.xml').getroot().tag == 'mujoco'
    gate = qualify(scenario)
    assert gate['structural_status'] == 'PASS' and gate['mjcf_exportable']
    assert gate['robot_training_status'] == 'NOT_RUN'
    assert any(item['code'] == 'collision_proxy_mismatch' for item in gate['issues'])
    bad_scene = {**scenario, 'obstacles': [scenario['obstacles'][0]] * 2}
    assert qualify(bad_scene)['structural_status'] == 'FAIL'
    robot_rollout = json.loads((ROOT / 'examples/physical-world/s10_unactuated_rollout.json').read_text())
    assert len(robot_rollout['frames']) == 60 and robot_rollout['source_urdf_sha256'] == robot['source_sha256']
    assert robot_rollout['control'] == 'none_unactuated' and not robot_rollout['robot_deployable']
    receipt = json.loads((ROOT / 'examples/gx10-nemotron/receipt.json').read_text())
    assert receipt['status'] == 'GX10_NEMOTRON_CORE_INFERENCE_PASS'
    assert receipt['worldstage_health']['model_connected'] and len(receipt['model_file_sha256']) == 64
    assert len(receipt['worldstage_runs']) >= 2 and all(item['generated_object']['provenance']['mode'] == 'nvidia_nemotron' for item in receipt['worldstage_runs'])
    ramp = generate_object('低摩擦斜坡', allow_model=False)['object']
    ball = generate_object('可滚动的金属球', allow_model=False)['object']
    assert ramp['kind'] == 'ramp' and ramp['mass_kg'] == 0 and ramp['yaw'] != 0
    assert ball['kind'] == 'sphere' and ball['mass_kg'] > 0 and ball['position'][2] == 3
    for theme, phrase in [('forest', '夜光森林'), ('ocean', '海底藏书城'), ('city', '未来浮空城')]:
        result = build(phrase, allow_model=False)
        assert result['plan']['theme'] == theme
        assert result['manifest']['mode'] == 'template'
        assert result['evaluation']['status'] == 'PASS'
        folder = ROOT / 'runs' / result['run_id']
        for filename, digest in result['manifest']['artifacts_sha256'].items():
            assert hashlib.sha256((folder / filename).read_bytes()).hexdigest() == digest
    failed = verify({'objects': [{'id': 'duplicate', 'position': [0, 0, 0]}] * 6}, {'events': []}, {'beats': []})
    assert failed['status'] == 'FAIL'
    example = ROOT / 'examples' / 'forest-run'
    manifest = json.loads((example / 'manifest.json').read_text())
    for filename, digest in manifest['artifacts_sha256'].items():
        assert hashlib.sha256((example / filename).read_bytes()).hexdigest() == digest
    print('PASS: build, 13 skills, S10 source SHA, scene gate, physical world assets, 3 themes, negative contract, artifact hashes')


if __name__ == '__main__':
    main()
