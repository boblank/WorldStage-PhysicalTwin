"""Reproducible task and failure-case benchmark for the WorldStage Skills.

This is an offline contract benchmark. Browser puzzle completion and live model
quality are separate gates, never inferred from passing source checks.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from behavior_benchmark import run as run_behavior_benchmark
from physical_cli import audit
from pipeline import ROOT, build, compose, intake, interactions, narrate, plan, verify, _write
from robot_world import base_scenario, generate_object, scenario_mjcf
from scene_gate import qualify

SKILLS = sorted(path.parent.name for path in (ROOT / 'skills').glob('*/SKILL.md'))


def check(name: str, procedure) -> dict:
    start = time.monotonic()
    try:
        passed, detail = procedure()
        status = 'PASS' if passed else 'FAIL'
    except Exception as exc:
        status, detail = 'FAIL', f'{type(exc).__name__}: {str(exc)[:180]}'
    return {'skill': name, 'status': status, 'detail': detail, 'duration_ms': round((time.monotonic() - start) * 1000)}


def _robot() -> tuple[bool, str]:
    details = []
    for name, minimum in [('S10', 19), ('TurtleBot3-Burger', 6)]:
        urdf = ROOT / f'public/robots/{name}-source.urdf'
        meta = json.loads((ROOT / f'public/robots/{name}-collision.json').read_text())
        root = ET.parse(urdf).getroot()
        joints = root.findall('joint')
        if hashlib.sha256(urdf.read_bytes()).hexdigest() != meta['source_sha256'] or len(joints) < minimum:
            return False, f'{name} source/joint mismatch'
        if any(j.get('type') in ('revolute', 'prismatic') and j.find('limit') is None for j in joints):
            return False, f'{name} missing joint limit'
        details.append(f'{name}:{len(joints)} joints')
    return True, ', '.join(details)


def _worldgen() -> tuple[bool, str]:
    manifest = json.loads((ROOT / 'public/worldgen/manifest.json').read_text())
    good = all(hashlib.sha256((ROOT / 'public/worldgen' / asset['file']).read_bytes()).hexdigest() == asset['sha256'] for asset in manifest['assets'])
    source = json.loads((ROOT / 'public/worldgen/robot-test-arena/source.json').read_text())
    image = ROOT / 'public/worldgen/robot-test-arena/reference.png'
    good &= hashlib.sha256(image.read_bytes()).hexdigest() == source['input_image_sha256']
    return good and len(manifest['assets']) == 7, '7 GLB SHA-256 and input image SHA-256'


def _scene_gate() -> tuple[bool, str]:
    world = json.loads((ROOT / 'public/worldgen/robot-test-arena/scene.json').read_text())
    source = json.loads((ROOT / 'public/worldgen/robot-test-arena/source.json').read_text())
    positive = qualify(world, source)
    bad = {**world, 'obstacles': [world['obstacles'][0]] * 2}
    negative = qualify(bad, source)
    good = positive['structural_status'] == 'PASS' and negative['structural_status'] == 'FAIL' and positive['robot_training_status'] != 'PASS'
    return good, 'positive structural scene; duplicate-ID negative; training remains gated'


def _physical() -> tuple[bool, str]:
    report = audit(grid=5)
    good = report['total_triangles'] > 100000 and len(report['assets']) == 7 and report['source_units'] == 'unknown' and report['robot_training_status'] == 'BLOCKED'
    return good, f"{report['total_triangles']} actual triangles; {len(report['mismatched_assets'])}/7 proxy discrepancies; metric unknown"


def _xml() -> tuple[bool, str]:
    world = base_scenario()
    root = ET.fromstring(scenario_mjcf(world))
    geoms = root.findall('.//geom')
    return root.tag == 'mujoco' and len(geoms) >= len(world['obstacles']) + 1, f'{len(geoms)} MJCF geoms parse; robot dynamics outside scope'


def _rollout() -> tuple[bool, str]:
    path = ROOT / 'examples/physical-world/s10_unactuated_rollout.json'
    data = json.loads(path.read_text())
    valid = len(data['frames']) >= 60 and data['control'] == 'none_unactuated' and data['robot_deployable'] is False
    valid &= hashlib.sha256((ROOT / 'public/robots/S10-source.urdf').read_bytes()).hexdigest() == data['source_urdf_sha256']
    return valid, f"{len(data['frames'])} frames; unactuated and non-deployable label"


def _browser(kind: str) -> tuple[bool, str]:
    folder = ROOT / 'examples/skill-benchmark'
    receipt = json.loads((folder / 'browser_e2e_receipt.json').read_text())
    compressed = (folder / receipt['trajectory_file']).read_bytes()
    raw = gzip.decompress(compressed)
    if hashlib.sha256(compressed).hexdigest() != receipt['trajectory_gzip_sha256'] or hashlib.sha256(raw).hexdigest() != receipt['trajectory_sha256']:
        return False, 'browser trajectory hash mismatch'
    record = json.loads(raw)
    if kind == 'avatar':
        snapshot = (folder / receipt['turtlebot3_snapshot_file']).read_bytes()
        turtle_ok = hashlib.sha256(snapshot).hexdigest() == receipt['turtlebot3_snapshot_sha256'] and b'ROBOTIS TurtleBot3 Burger' in snapshot
        source_sha = hashlib.sha256((ROOT / 'public/robots/S10-source.urdf').read_bytes()).hexdigest()
        valid = turtle_ok and record['robot']['name'] == 'DEEPRobotics S10' and record['source_urdf_sha256'] == source_sha
        return valid, 'real browser TurtleBot3 snapshot + S10 trajectory; both are kinematic proxies'
    events = [entry for entry in record['events'] if entry['type'].startswith('puzzle') or entry['type'] == 'truth_selected']
    outcomes = [(entry['type'], entry.get('outcome')) for entry in events]
    required = [('puzzle_chest', 'power_key_obtained'), ('puzzle_monster', 'calmed_with_generated_ramp'),
                ('puzzle_answer', 'wrong'), ('puzzle_answer', 'calibrate'), ('truth_selected', 'mirror')]
    cursor = 0
    for item in outcomes:
        if cursor < len(required) and item == required[cursor]:
            cursor += 1
    valid = cursor == len(required) and record['story_clues'] == ['avatar', 'chest', 'monster', 'npc', 'gate']
    valid &= record['truth_route'] == 'mirror' and len(record['frames']) >= 100 and all(record['puzzle_flags'].values())
    valid &= record['worldgen_source']['mesh_collider_count'] == 7
    return valid, f"{len(record['frames'])} browser frames, 5/5 clues, wrong answer rejected, mirror ending, 7 mesh colliders"


@lru_cache(maxsize=1)
def _behavior_report() -> dict:
    return run_behavior_benchmark()


def _behavior_skill(name: str) -> tuple[bool, str]:
    report = _behavior_report()
    groups = {
        'behavior-episode-capture': {'recorded_browser_trace', 'human_intent_provenance'},
        'nemotron-behavior-audit': {'stuck_vs_progress', 'scene_gate_cannot_be_overridden'},
        'sim-dataset-curation': {'human_intent_provenance', 'nonmonotonic_time_rejected', 'scene_gate_cannot_be_overridden'},
        'behavior-benchmark': {item['case'] for item in report['cases']},
    }
    relevant = [item for item in report['cases'] if item['case'] in groups[name]]
    return bool(relevant) and all(item['status'] == 'PASS' for item in relevant), f"{len(relevant)} offline cases; live Nemotron quality NOT_RUN here"


def run() -> dict:
    brief = intake('夜光森林里的记忆之门')
    planned = plan(brief, allow_model=False)
    scene = compose(planned)
    events = interactions(scene)
    story = narrate(planned, scene)
    rows = [
        check('world-intake', lambda: (brief['prompt'] == '夜光森林里的记忆之门' and intake('x' * 350)['prompt'] == 'x' * 300, 'Unicode preserved; long input bounded to 300')),
        check('world-plan', lambda: (planned['theme'] == 'forest' and planned['provenance']['mode'] == 'template' and len(planned['objects']) == 6, 'forest intent; six objects; explicit template provenance')),
        check('world-compose', lambda: (len({o['id'] for o in scene['objects']}) == 6 and all(abs(o['position'][0]) <= 5 and abs(o['position'][2]) <= 5 for o in scene['objects']), 'six unique in-bounds objects')),
        check('world-interact', lambda: ({e['target'] for e in events['events']} == {o['id'] for o in scene['objects']} and all(e['reversible'] for e in events['events']), 'interaction targets cover all objects; reversible')),
        check('world-narrate', lambda: ({b['target'] for b in story['beats']} == {o['id'] for o in scene['objects']} and len(story['ending']) > 8, 'story beats cover all objects')),
        check('world-verify', lambda: (verify(scene, events, story)['status'] == 'PASS' and verify({**scene, 'objects': scene['objects'][:5] + scene['objects'][:1]}, events, story)['status'] == 'FAIL', 'valid case accepted; duplicate ID rejected')),
        check('world-orchestrate', lambda: _orchestrate()),
        check('robot-urdf-import', _robot),
        check('worldgen-visual-intake', _worldgen),
        check('physical-world-author', _physical),
        check('physics-scenario-export', _xml),
        check('scene-readiness-gate', _scene_gate),
        check('rollout-capture', _rollout),
        check('nemotron-service-audit', lambda: _nemotron_receipt()),
        check('avatar-casting', lambda: _browser('avatar')),
        check('memory-puzzle-director', lambda: _browser('puzzle')),
        check('behavior-episode-capture', lambda: _behavior_skill('behavior-episode-capture')),
        check('nemotron-behavior-audit', lambda: _behavior_skill('nemotron-behavior-audit')),
        check('sim-dataset-curation', lambda: _behavior_skill('sim-dataset-curation')),
        check('behavior-benchmark', lambda: _behavior_skill('behavior-benchmark')),
    ]
    rows.sort(key=lambda row: row['skill'])
    if [row['skill'] for row in rows] != SKILLS:
        raise ValueError(f'benchmark inventory mismatch: benchmark={len(rows)}, skills={len(SKILLS)}')
    counts = {status: sum(row['status'] == status for row in rows) for status in ('PASS', 'FAIL', 'NOT_RUN')}
    return {'schema': 'worldstage.skills_benchmark.v1', 'scope': 'offline_skill_contracts_source_provenance_and_negative_cases',
            'skill_count': len(SKILLS), 'counts': counts, 'coverage_fraction': round((counts['PASS'] + counts['FAIL']) / len(SKILLS), 3),
            'status': 'FAIL' if counts['FAIL'] else 'PARTIAL_SKILL_GATES' if counts['NOT_RUN'] else 'PASS_RECORDED_TASK_CASES',
            'model_quality': 'NOT_RUN_USE_model_cli_benchmark_AND_behavior_benchmark_live', 'robot_sim2real': 'NOT_RUN', 'skills': rows}


def _orchestrate() -> tuple[bool, str]:
    result = build('潮汐海底档案馆', allow_model=False)
    folder = ROOT / 'runs' / result['run_id']
    good = result['evaluation']['status'] == 'PASS' and result['plan']['theme'] == 'ocean'
    good &= all(hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha for name, sha in result['manifest']['artifacts_sha256'].items())
    return good, f"ocean run {result['run_id']}; six artifact SHA-256 checked"


def _nemotron_receipt() -> tuple[bool, str]:
    path = ROOT / 'examples/gx10-nemotron/receipt.json'
    data = json.loads(path.read_text())
    return data['status'] == 'GX10_NEMOTRON_CORE_INFERENCE_PASS' and len(data['model_file_sha256']) == 64, 'recorded GX10 inference receipt; current service is a separate live gate'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples/skill-benchmark/report.json')
    args = parser.parse_args()
    report = run()
    _write(args.output, report)
    print(json.dumps({'report': str(args.output), **report}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if report['counts']['FAIL'] else 0)


if __name__ == '__main__':
    main()
