"""Pin ROBOTIS TurtleBot3 Burger and derive a mesh-free collision model.

The source is retained verbatim. We only resolve its empty namespace xacro
parameter and remove visual meshes in the derived file.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from import_s10 import origin, vec


ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'public/robots'
REVISION = 'fc817ce3073af1d6032397c64504134882af5e9a'
BASE = f'https://raw.githubusercontent.com/ROBOTIS-GIT/turtlebot3/{REVISION}'
SOURCE = DEST / 'TurtleBot3-Burger-source.urdf'
LICENSE = DEST / 'LICENSE-TurtleBot3.txt'


def obtain() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        SOURCE.write_bytes(urllib.request.urlopen(f'{BASE}/turtlebot3_description/urdf/turtlebot3_burger.urdf', timeout=30).read())
    if not LICENSE.exists():
        LICENSE.write_bytes(urllib.request.urlopen(f'{BASE}/LICENSE', timeout=30).read())


def main() -> None:
    obtain()
    source = SOURCE.read_text()
    resolved = source.replace('${namespace}', '')
    root = ET.fromstring(resolved)
    for node in list(root):
        if node.tag.startswith('{http://ros.org/wiki/xacro}'):
            root.remove(node)
    links = []
    for link in root.findall('link'):
        for visual in list(link.findall('visual')):
            link.remove(visual)
        mass = link.find('./inertial/mass')
        collisions = []
        for collision in link.findall('collision'):
            geometry = collision.find('geometry')
            shape = next(iter(geometry), None) if geometry is not None else None
            if shape is None or shape.tag not in ('box', 'cylinder', 'sphere'):
                raise ValueError(f'unsupported collision geometry: {link.get("name")}')
            collisions.append({'shape': shape.tag, 'params': {k: vec(v) if k == 'size' else float(v) for k, v in shape.attrib.items()}, 'origin': origin(collision.find('origin'))})
        links.append({'name': link.get('name'), 'mass_kg': float(mass.get('value')) if mass is not None else 0, 'collisions': collisions})
    joints = []
    for joint in root.findall('joint'):
        limit = joint.find('limit')
        joints.append({'name': joint.get('name'), 'type': joint.get('type'), 'parent': joint.find('parent').get('link'), 'child': joint.find('child').get('link'), 'origin': origin(joint.find('origin')), 'axis': vec(joint.find('axis').get('xyz')) if joint.find('axis') is not None else [0, 0, 1], 'limit': dict(limit.attrib) if limit is not None else None})
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(DEST / 'TurtleBot3-Burger-collision.urdf', encoding='utf-8', xml_declaration=True)
    data = {'name': 'ROBOTIS TurtleBot3 Burger', 'representation': 'collision_geometry_from_official_urdf', 'source_repo': 'https://github.com/ROBOTIS-GIT/turtlebot3', 'source_revision': REVISION, 'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'license': 'Apache-2.0', 'source_file': SOURCE.name, 'collision_file': 'TurtleBot3-Burger-collision.urdf', 'coordinate_system': 'z_up_meters', 'total_mass_kg': round(sum(link['mass_kg'] for link in links), 6), 'links': links, 'joints': joints}
    (DEST / 'TurtleBot3-Burger-collision.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f"{len(links)} links, {len(joints)} joints, {sum(len(x['collisions']) for x in links)} colliders, {data['total_mass_kg']} kg, SHA {data['source_sha256']}")


if __name__ == '__main__':
    main()
