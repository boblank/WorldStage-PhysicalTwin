"""Audit actual WorldGen GLB geometry against the exported MJCF box proxies.

The audit compares sampled top surfaces in source display coordinates. A single
measured anchor can produce a provisional scale receipt. Neither operation
validates contact dynamics or certifies robot training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from pipeline import ROOT, _write

ASSET_DIR = ROOT / 'public/worldgen'
MANIFEST = ASSET_DIR / 'manifest.json'
SCENE = ASSET_DIR / 'robot-test-arena/scene.json'


def _glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from('<III', raw)
    if magic != 0x46546c67 or version != 2 or length != len(raw):
        raise ValueError(f'invalid GLB header: {path.name}')
    pos, data = 12, {}
    while pos < len(raw):
        size, kind = struct.unpack_from('<II', raw, pos)
        pos += 8
        data[kind] = raw[pos:pos + size]
        pos += size
    return json.loads(data[0x4e4f534a]), data[0x004e4942]


def _accessor(document: dict, binary: bytes, index: int) -> list:
    item = document['accessors'][index]
    if item.get('sparse'):
        raise ValueError('sparse accessor unsupported by this audit')
    view = document['bufferViews'][item['bufferView']]
    count = {'SCALAR': 1, 'VEC3': 3}[item['type']]
    fmt = {5126: 'f', 5125: 'I', 5123: 'H', 5121: 'B'}[item['componentType']]
    width = struct.calcsize('<' + fmt * count)
    stride = view.get('byteStride', width)
    start = view.get('byteOffset', 0) + item.get('byteOffset', 0)
    return [struct.unpack_from('<' + fmt * count, binary, start + i * stride) for i in range(item['count'])]


def _asset_geometry(asset: dict, manifest: dict) -> tuple[list[tuple[float, float, float]], list[int]]:
    path = ASSET_DIR / asset['file']
    if hashlib.sha256(path.read_bytes()).hexdigest() != asset['sha256']:
        raise ValueError(f'asset SHA mismatch: {asset["id"]}')
    doc, binary = _glb(path)
    if len(doc['nodes']) != 1 or len(doc['meshes']) != 1 or len(doc['meshes'][0]['primitives']) != 1 or doc['nodes'][0].get('matrix') or doc['nodes'][0].get('rotation'):
        raise ValueError(f'GLB layout unsupported by this audit: {asset["id"]}')
    primitive = doc['meshes'][0]['primitives'][0]
    if primitive.get('mode', 4) != 4:
        raise ValueError(f'non-triangle primitive: {asset["id"]}')
    raw_positions = _accessor(doc, binary, primitive['attributes']['POSITION'])
    raw_indices = _accessor(doc, binary, primitive['indices']) if 'indices' in primitive else [(i,) for i in range(len(raw_positions))]
    indices = [i[0] for i in raw_indices]
    if len(indices) % 3 or any(i >= len(raw_positions) for i in indices):
        raise ValueError(f'invalid triangle indices: {asset["id"]}')
    matrix = asset['transform']
    scale, offset = manifest['display_scale'], manifest['display_offset']
    vertices = []
    for x, y, z in raw_positions:
        tx = matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]
        ty = matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]
        tz = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3]
        vertices.append((tx * scale + offset[0], tz * scale + offset[2], ty * scale + offset[1]))
    return vertices, indices


def _top_at(vertices: list, indices: list, x: float, y: float) -> float | None:
    highest = None
    for i in range(0, len(indices), 3):
        a, b, c = (vertices[indices[i + j]] for j in range(3))
        if x < min(a[0], b[0], c[0]) or x > max(a[0], b[0], c[0]) or y < min(a[1], b[1], c[1]) or y > max(a[1], b[1], c[1]):
            continue
        determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(determinant) < 1e-10:
            continue
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / determinant
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / determinant
        if u < -1e-7 or v < -1e-7 or u + v > 1 + 1e-7:
            continue
        z = u * a[2] + v * b[2] + (1 - u - v) * c[2]
        highest = z if highest is None else max(highest, z)
    return highest


def audit(grid: int = 5) -> dict:
    manifest_bytes = MANIFEST.read_bytes()
    scene_bytes = SCENE.read_bytes()
    manifest, scene = json.loads(manifest_bytes), json.loads(scene_bytes)
    if manifest['asset_count'] != len(manifest['assets']):
        raise ValueError('asset count mismatch')
    rows = []
    for asset in manifest['assets']:
        index = int(asset['id'].split('_')[-1])
        proxy = next(item for item in scene['obstacles'] if item['worldgen_object_index'] == index)
        vertices, indices = _asset_geometry(asset, manifest)
        bounds = [[min(v[axis] for v in vertices), max(v[axis] for v in vertices)] for axis in range(3)]
        px = proxy['position'][0] * manifest['display_scale'] + manifest['display_offset'][0]
        py = proxy['position'][1] * manifest['display_scale'] + manifest['display_offset'][2]
        sx, sy, sz = [v * manifest['display_scale'] for v in proxy['size']]
        box_top = proxy['position'][2] * manifest['display_scale'] + manifest['display_offset'][1] + sz / 2
        samples = []
        for j in range(grid):
            for k in range(grid):
                x = px + sx * ((j + .5) / grid - .5)
                y = py + sy * ((k + .5) / grid - .5)
                hit = _top_at(vertices, indices, x, y)
                if hit is not None:
                    samples.append(abs(hit - box_top))
        rows.append({'id': asset['id'], 'sha256': asset['sha256'], 'vertices': len(vertices), 'triangles': len(indices) // 3,
                     'bounds_display_units_xyz': [[round(v, 4) for v in pair] for pair in bounds],
                     'proxy_top_display_units': round(box_top, 4), 'grid_samples': grid * grid,
                     'mesh_top_hits': len(samples), 'coverage_fraction': round(len(samples) / (grid * grid), 3),
                     'mean_abs_top_difference_display_units': round(sum(samples) / len(samples), 4) if samples else None,
                     'max_abs_top_difference_display_units': round(max(samples), 4) if samples else None})
    mismatch = [row['id'] for row in rows if row['coverage_fraction'] < .9 or (row['max_abs_top_difference_display_units'] or 0) > .05]
    return {'schema': 'worldstage.physical_audit.v1', 'status': 'REVIEW_MESH_PROXY_DIFFERENCE' if mismatch else 'GEOMETRY_SAMPLES_WITHIN_THRESHOLD',
            'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'source_scene_sha256': hashlib.sha256(scene_bytes).hexdigest(),
            'source_units': 'unknown', 'display_scale_is_metric': False, 'grid': f'{grid}x{grid}', 'threshold_display_units': .05,
            'total_triangles': sum(row['triangles'] for row in rows), 'mismatched_assets': mismatch, 'assets': rows,
            'method': 'vertical triangle surface sampling versus exported axis-aligned box top; no Rapier or MuJoCo dynamics',
            'robot_training_status': 'BLOCKED', 'real_contact_status': 'NOT_RUN'}


def calibrate(args: argparse.Namespace) -> dict:
    result = audit(grid=3)
    row = next(item for item in result['assets'] if item['id'] == args.asset)
    axis = {'x': 0, 'y': 1, 'z': 2}[args.axis]
    source_length = row['bounds_display_units_xyz'][axis][1] - row['bounds_display_units_xyz'][axis][0]
    if not math.isfinite(args.measured_length_m) or args.measured_length_m <= 0 or source_length <= 0:
        raise ValueError('Measurement and source extent must be positive finite values')
    if not args.evidence:
        raise ValueError('Measurement evidence reference is required')
    return {'schema': 'worldstage.metric_calibration.v1', 'status': 'PROVISIONAL_SINGLE_ANCHOR', 'asset': args.asset,
            'axis': args.axis, 'measured_length_m': args.measured_length_m, 'source_length_display_units': round(source_length, 5),
            'metres_per_display_unit': round(args.measured_length_m / source_length, 6), 'measurement_evidence': args.evidence,
            'source_manifest_sha256': result['source_manifest_sha256'], 'robot_training_status': 'BLOCKED',
            'next_gate': 'independent second anchor, physical contact/friction tests, cross-engine robot rollout'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    item = sub.add_parser('audit')
    item.add_argument('--grid', type=int, default=5)
    item.add_argument('--output', type=Path, default=ROOT / 'examples/physical-world/worldgen_physical_audit.json')
    item = sub.add_parser('calibrate')
    item.add_argument('--asset', required=True, choices=[f'object_{i:04d}' for i in range(7)])
    item.add_argument('--axis', required=True, choices=['x', 'y', 'z'])
    item.add_argument('--measured-length-m', required=True, type=float)
    item.add_argument('--evidence', required=True, help='Reference to measurement photo/log, not a guessed value')
    item.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'audit' and not 2 <= args.grid <= 11:
        parser.error('--grid must be between 2 and 11')
    report = audit(args.grid) if args.command == 'audit' else calibrate(args)
    _write(args.output, report)
    print(json.dumps({'report': str(args.output), **report}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
