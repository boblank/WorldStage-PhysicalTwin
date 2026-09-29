"""Compile the generated world and the S10 collision URDF in MuJoCo.

Requires `mujoco` in a separate Python 3.11+ environment. This is a gravity/contact
smoke, not locomotion, policy performance, or hardware evidence.
"""
from __future__ import annotations

import json
import hashlib
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco

from pipeline import ROOT


EXAMPLE = ROOT / 'examples/physical-world'
ROBOT = ROOT / 'public/robots/S10-collision.urdf'


def base_inertial() -> dict[str, str]:
    root = ET.parse(ROBOT).getroot()
    link = root.find("./link[@name='base_link']/inertial")
    origin = link.find('origin')
    mass = link.find('mass').get('value')
    inertia = link.find('inertia')
    return {'pos': origin.get('xyz'), 'mass': mass, 'fullinertia': ' '.join(inertia.get(k) for k in ('ixx', 'iyy', 'izz', 'ixy', 'ixz', 'iyz'))}


def combined_xml() -> str:
    model = mujoco.MjModel.from_xml_path(str(ROBOT))
    with tempfile.TemporaryDirectory() as temp:
        canonical = Path(temp) / 'robot.xml'
        mujoco.mj_saveLastXML(str(canonical), model)
        robot_root = ET.parse(canonical).getroot()
    world_root = ET.parse(EXAMPLE / 'world.xml').getroot()
    robot_world = robot_root.find('worldbody')
    world = world_root.find('worldbody')
    base = ET.Element('body', name='base_link', pos='-11 0 0.42')
    ET.SubElement(base, 'freejoint')
    ET.SubElement(base, 'inertial', **base_inertial())
    for child in list(robot_world):
        robot_world.remove(child)
        base.append(child)
    world.append(base)
    ET.indent(world_root, space='  ')
    return ET.tostring(world_root, encoding='unicode') + '\n'


def run() -> dict:
    xml = combined_xml()
    (EXAMPLE / 'combined_s10_world.xml').write_text(xml)
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    cube_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'test-cube')
    robot_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, 'base_link')
    samples = []
    rollout_frames = []
    for step in range(240):
        mujoco.mj_step(model, data)
        if step % 4 == 3:
            rollout_frames.append({'time_s': round(data.time, 4), 'qpos': [round(float(v), 6) for v in data.qpos], 'qvel': [round(float(v), 6) for v in data.qvel], 'contact_count': int(data.ncon)})
        if step in (0, 49, 99, 149, 199, 239):
            samples.append({'time_s': round(data.time, 3), 'cube_height_m': round(float(data.xpos[cube_id, 2]), 5), 'robot_base_height_m': round(float(data.xpos[robot_id, 2]), 5), 'contact_count': int(data.ncon)})
    result = {'status': 'PASS', 'scope': 'generated_world_plus_unactuated_s10_gravity_contact_smoke', 'mujoco_version': mujoco.__version__, 'gravity_m_s2': model.opt.gravity.tolist(), 'nbody': int(model.nbody), 'ngeom': int(model.ngeom), 'nq': int(model.nq), 'nv': int(model.nv), 'samples': samples}
    assert model.nq >= 7 + 16
    assert samples[-1]['cube_height_m'] < samples[0]['cube_height_m']
    assert samples[-1]['contact_count'] > 0
    robot_data = json.loads((ROOT / 'public/robots/S10-collision.json').read_text())
    rollout = {'schema': 'worldstage.mujoco_unactuated.v1', 'source_urdf_sha256': robot_data['source_sha256'], 'world_xml_sha256': hashlib.sha256(xml.encode()).hexdigest(), 'mujoco_version': mujoco.__version__, 'control': 'none_unactuated', 'robot_deployable': False, 'timestep_s': float(model.opt.timestep), 'frames': rollout_frames}
    (EXAMPLE / 's10_unactuated_rollout.json').write_text(json.dumps(rollout, ensure_ascii=False, indent=2) + '\n')
    (EXAMPLE / 'mujoco_smoke.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
