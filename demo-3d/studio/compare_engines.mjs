/** Compare a matched free-fall cube in Rapier and MuJoCo; not a robot validation. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import RAPIER from '@dimforge/rapier3d-compat';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const scenario=JSON.parse(fs.readFileSync(path.join(root,'examples/physical-world/scenario.json')));
const mujoco=JSON.parse(fs.readFileSync(path.join(root,'examples/physical-world/mujoco_smoke.json')));
const test=scenario.obstacles.find(o=>o.id==='test-cube');
if(!test)throw new Error('test-cube missing');
await RAPIER.init();
const world=new RAPIER.World({x:0,y:-9.81,z:0});world.timestep=.005;
const gb=world.createRigidBody(RAPIER.RigidBodyDesc.fixed().setTranslation(0,-.1,0));
world.createCollider(RAPIER.ColliderDesc.cuboid(40,.1,40).setFriction(.8),gb);
const body=world.createRigidBody(RAPIER.RigidBodyDesc.dynamic().setTranslation(test.position[0],test.position[2],test.position[1]));
world.createCollider(RAPIER.ColliderDesc.cuboid(test.size[0]/2,test.size[2]/2,test.size[1]/2).setMass(test.mass_kg).setFriction(test.friction).setRestitution(0),body);
const picks=new Map();
for(let step=1;step<=240;step++){world.step();if([1,50,100,150,200,240].includes(step))picks.set(step,body.translation().y)}
const pairs=mujoco.samples.map((m,i)=>({time_s:m.time_s,mujoco_height_m:m.cube_height_m,rapier_height_m:Number(picks.get([1,50,100,150,200,240][i]).toFixed(5)),absolute_difference_m:Number(Math.abs(picks.get([1,50,100,150,200,240][i])-m.cube_height_m).toFixed(5))}));
const before=pairs.filter(p=>p.time_s<=.5);
const result={status:'PASS',scope:'single_rigid_cube_gravity_contact_comparison_only',engines:{mujoco:mujoco.mujoco_version,rapier:'@dimforge/rapier3d-compat'},gravity_m_s2:[0,0,-9.81],timestep_s:.005,object:{id:test.id,mass_kg:test.mass_kg,size_m:test.size,initial_height_m:test.position[2]},samples:pairs,mean_abs_difference_pre_contact_m:Number((before.reduce((a,p)=>a+p.absolute_difference_m,0)/before.length).toFixed(5)),robot_dynamics:'NOT_RUN'};
fs.writeFileSync(path.join(root,'examples/physical-world/sim2sim_drop_compare.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result,null,2));
