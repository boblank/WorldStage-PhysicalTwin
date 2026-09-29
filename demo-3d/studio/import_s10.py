"""Package the source S10 URDF and a collision-only derivative for the local demo."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ['S10_SOURCE_ROOT']) if os.getenv('S10_SOURCE_ROOT') else None
SOURCE = SOURCE_ROOT / 'src/S10_sdk_deploy/S10_description/s10_mjcf/urdf/S10.urdf' if SOURCE_ROOT else None
DEST = ROOT / 'public/robots'


def vec(text: str | None, default: str = '0 0 0') -> list[float]:
    return [float(v) for v in (text or default).split()]


def origin(node: ET.Element | None) -> dict[str, list[float]]:
    return {'xyz': vec(node.get('xyz') if node is not None else None), 'rpy': vec(node.get('rpy') if node is not None else None)}


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    source = SOURCE if SOURCE is not None and SOURCE.is_file() else DEST / 'S10-source.urdf'
    if not source.is_file():
        raise FileNotFoundError('S10 URDF is missing from both source workspace and package')
    if source != DEST / 'S10-source.urdf':
        shutil.copy2(source, DEST / 'S10-source.urdf')
        shutil.copy2(SOURCE_ROOT / 'LICENSE', DEST / 'LICENSE-S10.txt')
    tree = ET.parse(source)
    root = tree.getroot()
    for mujoco in list(root.findall('mujoco')):
        root.remove(mujoco)
    links = []
    for link in root.findall('link'):
        for visual in list(link.findall('visual')):
            link.remove(visual)
        mass = link.find('./inertial/mass')
        collisions = []
        for collision in link.findall('collision'):
            geom = collision.find('geometry')
            shape = next(iter(geom), None) if geom is not None else None
            if shape is None or shape.tag not in ('box', 'cylinder', 'sphere'):
                raise ValueError(f'unsupported collision geometry: {link.get("name")}')
            collisions.append({'shape': shape.tag, 'params': {k: float(v) if k != 'size' else vec(v) for k, v in shape.attrib.items()}, 'origin': origin(collision.find('origin'))})
        links.append({'name': link.get('name'), 'mass_kg': float(mass.get('value')) if mass is not None else 0, 'collisions': collisions})
    joints = []
    for joint in root.findall('joint'):
        limit = joint.find('limit')
        joints.append({'name': joint.get('name'), 'type': joint.get('type'), 'parent': joint.find('parent').get('link'), 'child': joint.find('child').get('link'), 'origin': origin(joint.find('origin')), 'axis': vec(joint.find('axis').get('xyz')) if joint.find('axis') is not None else [0, 0, 1], 'limit': dict(limit.attrib) if limit is not None else None})
    ET.indent(tree, space='  ')
    tree.write(DEST / 'S10-collision.urdf', encoding='utf-8', xml_declaration=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    result = {'name': 'DEEPRobotics S10', 'representation': 'collision_geometry_from_official_urdf', 'source_sha256': digest, 'license': 'BSD-3-Clause', 'source_file': 'S10-source.urdf', 'collision_file': 'S10-collision.urdf', 'coordinate_system': 'z_up_meters', 'total_mass_kg': round(sum(x['mass_kg'] for x in links), 6), 'links': links, 'joints': joints}
    (DEST / 'S10-collision.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f"{len(links)} links, {len(joints)} joints, {sum(len(x['collisions']) for x in links)} colliders, {result['total_mass_kg']} kg, SHA {digest}")


if __name__ == '__main__':
    main()
