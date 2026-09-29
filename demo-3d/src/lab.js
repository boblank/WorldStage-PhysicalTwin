import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import RAPIER from '@dimforge/rapier3d-compat';
import { buildWarehouse } from './warehouse.js';
import './lab.css';

const $ = id => document.getElementById(id);
const scene = new THREE.Scene(); scene.background = new THREE.Color('#53605e');
const camera = new THREE.PerspectiveCamera(53,1,.1,150); camera.position.set(-14,11,17);
const viewport = $('lab-viewport');
const renderer = new THREE.WebGLRenderer({antialias:true}); renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.5)); renderer.outputColorSpace=THREE.SRGBColorSpace; renderer.toneMapping=THREE.ACESFilmicToneMapping; renderer.toneMappingExposure=1.3;renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;viewport.appendChild(renderer.domElement);
const controls=new OrbitControls(camera,renderer.domElement); controls.enableDamping=true; controls.maxPolarAngle=Math.PI*.49; controls.minDistance=3; controls.maxDistance=55; controls.target.set(-1,0,-6);
scene.add(new THREE.HemisphereLight('#d9e6df','#3d514d',1.35)); const sun=new THREE.DirectionalLight('#fff0d2',2.5);sun.position.set(-12,20,16);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-25;sun.shadow.camera.right=25;sun.shadow.camera.top=25;sun.shadow.camera.bottom=-25;scene.add(sun);
let physics,worldData,urdf,robot,robotBody,robotCollider,controller,ground,sceneGateReport;let visuals=[],targets=[],trail=[],events=[],keys=new Set();let patrol=false,travelled=0,tickCount=0,contacts=0,lastPos=null;let avatar='s10',avatarHeight=.42,avatarSpeed=.042,storyStep=0,storyClues=[],storyTruth=null,generatedKind=null;
const ray=new THREE.Raycaster(),pointer=new THREE.Vector2(),colors={stone:'#9faab0',metal:'#81b5c1',wood:'#b9956a',grass:'#7fae8a',warning:'#d8a56b'};
function toast(t){$('toast').textContent=t;$('toast').classList.add('show');setTimeout(()=>$('toast').classList.remove('show'),3300)}
function resize(){const w=viewport.clientWidth,h=viewport.clientHeight;if(!w||!h)return;camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h,false)}new ResizeObserver(resize).observe(viewport);
function texture(name){const c=document.createElement('canvas');c.width=c.height=128;const ctx=c.getContext('2d');ctx.fillStyle=colors[name];ctx.fillRect(0,0,128,128);for(let i=0;i<160;i++){ctx.fillStyle=i%3?'#10273318':'#ffffff20';ctx.fillRect((i*53+name.length*19)%128,(i*97+name.length*11)%128,1+i%4,1+i%4)}const tex=new THREE.CanvasTexture(c);tex.wrapS=tex.wrapT=THREE.RepeatWrapping;tex.repeat.set(2,2);tex.colorSpace=THREE.SRGBColorSpace;return tex}
const mats=Object.fromEntries(Object.keys(colors).map(k=>[k,new THREE.MeshStandardMaterial({map:texture(k),roughness:k==='metal'?.3:.87,metalness:k==='metal'?.55:.05})]));
function decor(){ground=buildWarehouse(scene)}
async function loadWorldGenVisuals(){
  try{
    const [manifest,preview]=await Promise.all([
      fetch('/worldgen/manifest.json').then(r=>{if(!r.ok)throw new Error('manifest missing');return r.json()}),
      fetch('/worldgen/robot-test-arena/scene.json').then(r=>{if(!r.ok)throw new Error('scene missing');return r.json()})
    ]);
    const loader=new GLTFLoader(),display=new THREE.Group();
    display.name='Hyper3D WorldGen visual layer';
    display.position.set(...manifest.display_offset);
    display.scale.setScalar(manifest.display_scale);
    scene.add(display);
    const results=await Promise.allSettled(manifest.assets.map(async asset=>{
      const result=await loader.loadAsync('/worldgen/'+asset.file);
      result.scene.applyMatrix4(new THREE.Matrix4().set(...asset.transform.flat()));
      result.scene.traverse(node=>{if(node.isMesh){node.castShadow=true;node.receiveShadow=true}});
      display.add(result.scene);
      return result.scene;
    }));
    scene.updateMatrixWorld(true);
    let loaded=0,meshColliders=0,meshTriangles=0,boxFallbacks=0;
    for(const original of preview.obstacles){
      const result=results[original.worldgen_object_index];
      if(!result||result.status!=='fulfilled')continue;
      loaded++;
      const scale=manifest.display_scale,offset=manifest.display_offset;
      const o={...original,id:'worldgen-'+original.id,
        position:[original.position[0]*scale+offset[0],original.position[1]*scale+offset[2],original.position[2]*scale],
        size:original.size.map(v=>v*scale),mass_kg:0,
        physical_parameter_status:'estimated_from_visual_mesh',collision_proxy_status:'source_glb_trimesh_rapier'};
      const body=physics.createRigidBody(RAPIER.RigidBodyDesc.fixed());
      const meshes=[];result.value.traverse(node=>{if(node.isMesh&&node.geometry?.getAttribute('position'))meshes.push(node)});
      try{
        if(!meshes.length)throw new Error('GLB has no triangle mesh');
        for(const mesh of meshes){
          const position=mesh.geometry.getAttribute('position'),index=mesh.geometry.getIndex();
          const indices=index?Uint32Array.from(index.array):Uint32Array.from({length:position.count},(_,i)=>i);
          if(indices.length<3||indices.length%3)throw new Error('non-triangle geometry');
          const vertices=new Float32Array(position.count*3),point=new THREE.Vector3();
          for(let i=0;i<position.count;i++){
            point.fromBufferAttribute(position,i).applyMatrix4(mesh.matrixWorld);
            vertices.set([point.x,point.y,point.z],i*3);
          }
          physics.createCollider(RAPIER.ColliderDesc.trimesh(vertices,indices).setFriction(o.friction),body);
          meshColliders++;meshTriangles+=indices.length/3;
        }
        o.mesh_triangle_count=meshes.reduce((count,mesh)=>count+(mesh.geometry.getIndex()?.count||mesh.geometry.getAttribute('position').count)/3,0);
      }catch(error){
        physics.removeRigidBody(body);
        const fallback=physics.createRigidBody(RAPIER.RigidBodyDesc.fixed().setTranslation(o.position[0],o.position[2],o.position[1]));
        physics.createCollider(RAPIER.ColliderDesc.cuboid(o.size[0]/2,o.size[2]/2,o.size[1]/2).setFriction(o.friction),fallback);
        o.collision_proxy_status='bounding_box_fallback';o.collision_error=String(error.message||error);boxFallbacks++;
      }
      worldData.obstacles.push(o);
    }
    $('objects').textContent=`物体 ${worldData.obstacles.length}`;
    const failed=results.filter(r=>r.status==='rejected').length;
    $('worldgen-load').textContent=`WorldGen ${loaded}/${manifest.asset_count} GLB · ${meshColliders} 个原网格碰撞体 / ${meshTriangles} 三角面${boxFallbacks?' · '+boxFallbacks+' 个方盒回退':''}${failed?' · '+failed+' 个加载失败':''} · 米制未校准`;
    worldData.visual_source={provider:manifest.source_provider,original_export_sha256:manifest.original_export_sha256,source_image_sha256:manifest.source_image_sha256,physics_status:'rapier_source_glb_trimesh_metric_unverified_mjcf_proxy',asset_count:loaded,mesh_collider_count:meshColliders,mesh_triangle_count:meshTriangles,box_fallback_count:boxFallbacks,source_unit_status:manifest.display_scale_status};
    sceneGateReport=null;$('scene-gate-status').textContent='WorldGen 代理已进入场景，请复核';
  }catch(e){$('worldgen-load').textContent=`WorldGen 场景未加载：${e.message}`}
}
function visual(o){
  const [sx,sy,sz]=o.size, group=new THREE.Group(), material=mats[o.material]||mats.stone;
  const put=(geometry,mat,y=0)=>{const mesh=new THREE.Mesh(geometry,mat);mesh.position.y=y;mesh.castShadow=true;mesh.receiveShadow=true;group.add(mesh);return mesh};
  if(o.kind==='sphere')put(new THREE.SphereGeometry(sx/2,28,20),material);
  else if(o.kind==='pillar')put(new THREE.CylinderGeometry(sx/2,sx/2,sz,20),material);
  else if(o.kind==='tree'){
    put(new THREE.CylinderGeometry(sx*.12,sx*.18,sz*.65,12),mats.wood,-sz*.17);
    put(new THREE.IcosahedronGeometry(sx*.55,1),mats.grass,sz*.2);
    put(new THREE.IcosahedronGeometry(sx*.38,1),mats.grass,sz*.42);
  }else if(o.kind==='crystal'){
    put(new THREE.CylinderGeometry(sx*.48,sx*.57,sz*.15,6),mats.stone,-sz*.42);
    put(new THREE.OctahedronGeometry(sx*.68,0),new THREE.MeshStandardMaterial({color:'#8be7d7',emissive:'#58b9c3',emissiveIntensity:.36,metalness:.4,roughness:.2}),0).scale.y=sz/sx*.68;
  }else if(o.kind==='building'){
    put(new THREE.BoxGeometry(sx,sz*.78,sy),material,-sz*.11);
    put(new THREE.ConeGeometry(sx*.74,sz*.25,4),mats.warning,sz*.40).rotation.y=Math.PI/4;
  }else put(new THREE.BoxGeometry(sx,sz,sy),material);
  group.position.set(o.position[0],o.position[2],o.position[1]);
  if(o.kind==='ramp')group.rotation.z=o.yaw||0;
  return group;
}
function addObstacle(o){
  const mesh=visual(o);scene.add(mesh);
  const [sx,sy,sz]=o.size;
  const body=physics.createRigidBody((o.mass_kg>0?RAPIER.RigidBodyDesc.dynamic():RAPIER.RigidBodyDesc.fixed()).setTranslation(mesh.position.x,mesh.position.y,mesh.position.z));
  let desc=o.kind==='sphere'?RAPIER.ColliderDesc.ball(sx/2):(o.kind==='pillar'||o.kind==='tree')?RAPIER.ColliderDesc.cylinder(sz/2,sx/2):RAPIER.ColliderDesc.cuboid(sx/2,sz/2,sy/2);
  if(o.kind==='ramp')desc=desc.setRotation({x:0,y:0,z:Math.sin((o.yaw||0)/2),w:Math.cos((o.yaw||0)/2)});
  desc.setFriction(o.friction).setRestitution(.14);
  if(o.mass_kg>0)desc.setMass(o.mass_kg);
  const collider=physics.createCollider(desc,body);
  visuals.push({mesh,body,collider,id:o.id,dynamic:o.mass_kg>0});
  $('objects').textContent=`物体 ${worldData.obstacles.length}`;
}
const puzzleFlags={chest:false,monster:false,npc:false};
const storyObjects={};
function storyLabel(text,color='#f4d78e'){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;
  const context=canvas.getContext('2d');context.fillStyle='#102733dd';context.fillRect(0,18,512,92);
  context.strokeStyle=color;context.lineWidth=5;context.strokeRect(3,20,506,88);
  context.fillStyle=color;context.textAlign='center';context.font='bold 48px sans-serif';context.fillText(text,256,82);
  const map=new THREE.CanvasTexture(canvas);map.colorSpace=THREE.SRGBColorSpace;
  const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map,transparent:true,depthTest:false}));sprite.scale.set(2.5,.63,1);return sprite;
}
function storyWorld(){
  const wood=new THREE.MeshStandardMaterial({color:'#684f36',roughness:.78});
  const gold=new THREE.MeshStandardMaterial({color:'#e5b95e',metalness:.7,roughness:.32});
  const ruby=new THREE.MeshStandardMaterial({color:'#f8ad58',emissive:'#bb6d25',emissiveIntensity:.6});
  const chest=new THREE.Group();chest.position.set(-8,0,-5);
  const base=new THREE.Mesh(new THREE.BoxGeometry(.95,.54,.72),wood);base.position.y=.29;base.castShadow=true;chest.add(base);
  for(const x of [-.39,.39]){const band=new THREE.Mesh(new THREE.BoxGeometry(.09,.6,.75),gold);band.position.set(x,.32,0);chest.add(band)}
  const lid=new THREE.Mesh(new THREE.BoxGeometry(1.02,.2,.78),wood);lid.position.y=.64;lid.castShadow=true;chest.add(lid);
  const key=new THREE.Mesh(new THREE.OctahedronGeometry(.19),ruby);key.position.set(0,1.12,0);chest.add(key);
  const chestGlow=new THREE.PointLight('#f3bd68',7,4);chestGlow.position.set(0,1.2,0);chest.add(chestGlow);
  const chestLabel=storyLabel('01 / 记忆宝箱');chestLabel.position.y=1.7;chest.add(chestLabel);scene.add(chest);
  storyObjects.chest={group:chest,lid,key,label:chestLabel,x:-8,z:-5,radius:1.45,name:'记忆宝箱'};
  const monster=new THREE.Group();monster.position.set(6,0,-8);
  const body=new THREE.Mesh(new THREE.IcosahedronGeometry(.56,1),new THREE.MeshStandardMaterial({color:'#655a83',roughness:.65}));body.position.y=.62;body.castShadow=true;monster.add(body);
  for(const dx of [-.2,.2]){
    const eye=new THREE.Mesh(new THREE.SphereGeometry(.11,12,10),new THREE.MeshBasicMaterial({color:'#f8dca6'}));eye.position.set(dx,.78,.47);monster.add(eye);
    const pupil=new THREE.Mesh(new THREE.SphereGeometry(.047,10,8),new THREE.MeshBasicMaterial({color:'#20333c'}));pupil.position.set(dx,.78,.56);monster.add(pupil);
    const horn=new THREE.Mesh(new THREE.ConeGeometry(.13,.4,8),gold);horn.position.set(dx*1.5,1.25,0);monster.add(horn);
  }
  const monsterLabel=storyLabel('02 / 守门兽','#d4b8ff');monsterLabel.position.y=1.9;monster.add(monsterLabel);
  const monsterGlow=new THREE.PointLight('#ad8fdd',9,6);monsterGlow.position.set(0,1,0);monster.add(monsterGlow);scene.add(monster);
  storyObjects.monster={group:monster,body,glow:monsterGlow,x:6,z:-8,radius:1.6,name:'守门兽'};
  const npc=new THREE.Group();npc.position.set(2,0,-17.1);
  const cloak=new THREE.Mesh(new THREE.ConeGeometry(.38,1.5,8),new THREE.MeshStandardMaterial({color:'#345762',roughness:.9,emissive:'#14495c',emissiveIntensity:.25}));cloak.position.y=.8;cloak.castShadow=true;npc.add(cloak);
  const head=new THREE.Mesh(new THREE.SphereGeometry(.24,16,12),new THREE.MeshStandardMaterial({color:'#a3c1b8',roughness:.8}));head.position.y=1.57;npc.add(head);
  const npcLabel=storyLabel('03 / 隐藏见证者','#9debd8');npcLabel.position.y=2.27;npc.add(npcLabel);
  const npcGlow=new THREE.PointLight('#7ce9cf',8,6);npcGlow.position.set(0,1.4,0);npc.add(npcGlow);scene.add(npc);
  storyObjects.npc={group:npc,label:npcLabel,x:2,z:-17.1,radius:1.7,name:'隐藏见证者'};
  for(const [id,obj] of Object.entries(storyObjects)){
    const size=id==='chest'?[.95,.72,.7]:id==='monster'?[.8,.8,1.15]:[.75,.75,1.6];
    const obstacle={id:`puzzle-${id}`,name:obj.name,kind:'box',position:[obj.x,obj.z,size[2]/2],size,yaw:0,mass_kg:0,friction:.8,material:'wood',physical_parameter_status:'design_assumption_unmeasured'};
    worldData.obstacles.push(obstacle);
    const fixed=physics.createRigidBody(RAPIER.RigidBodyDesc.fixed().setTranslation(obj.x,size[2]/2,obj.z));
    physics.createCollider(RAPIER.ColliderDesc.cuboid(size[0]/2,size[2]/2,size[1]/2).setFriction(.8),fixed);
  }
  $('objects').textContent=`物体 ${worldData.obstacles.length}`;
}
function logPuzzle(type,id,outcome){const p=robotBody.translation();events.push({time_s:tickCount/60,type,id,outcome,position_m:[p.x,p.z,p.y],avatar,source:'human_interaction_in_browser_proxy',worldgen_export_sha256:worldData.visual_source?.original_export_sha256||null})}
function nearestStoryObject(){if(!robotBody)return null;const p=robotBody.translation();let best=null;for(const [id,o] of Object.entries(storyObjects)){if((id==='chest'&&puzzleFlags.chest)||(id==='monster'&&puzzleFlags.monster)||(id==='npc'&&puzzleFlags.npc))continue;const distance=Math.hypot(p.x-o.x,p.z-o.z);if(distance<o.radius&&(!best||distance<best.distance))best={id,...o,distance}}return best}
function updatePuzzleSignal(){if(!robotBody)return;const near=nearestStoryObject(),p=robotBody.translation(),button=$('interact-near');button.disabled=!near;button.textContent=near?`与${near.name}互动 · E`:'靠近发光线索后按 E';
  if(near){$('puzzle-signal').textContent=`${near.name}就在身边。按 E 读取它留下的线索。`;return}
  if(storyStep===2)$('puzzle-signal').textContent='第一条信号来自西侧入口，坐标 (-8, -5)：发光宝箱。';
  else if(storyStep===3)$('puzzle-signal').textContent='守门兽在试验仓东侧 (6, -8)。它需要一段新生成的斜坡。';
  else if(storyStep===4){const d=Math.hypot(p.x-2,p.z+17.1);$('puzzle-signal').textContent=d<5?'黄栏后有微弱信号。绕到栏杆另一侧寻找见证者。':'隐藏的见证者在北侧黄栏后；信号来自 (2, -17)。'}
  else if(storyStep===5)$('puzzle-signal').textContent='线索已齐。复核物理场景，辨认哪条真相仍缺实验证据。';
}
function interactNear(){const near=nearestStoryObject();if(!near){toast('请先靠近一件发光物体');return}interactStory(near.id)}
function interactStory(id){
  if(storyStep<2){toast('请先确认分身');return}
  patrol=false;targets=[];$('patrol').textContent='开始自动探索';
  if(id==='chest'){
    if(storyStep!==2){toast('宝箱此刻没有新线索');return}
    puzzleFlags.chest=true;storyObjects.chest.lid.rotation.z=-.48;storyObjects.chest.key.visible=false;
    logPuzzle('puzzle_chest','chest','power_key_obtained');advanceStory('chest');return;
  }
  if(id==='monster'){
    if(storyStep!==3){toast('守门兽还在等待前面的记忆');return}
    if(generatedKind!=='ramp'){logPuzzle('puzzle_monster','monster','requires_generated_ramp');toast('守门兽指向左侧：请生成一段斜坡，再来与它互动');return}
    puzzleFlags.monster=true;storyObjects.monster.body.material.color.set('#53877b');storyObjects.monster.glow.color.set('#86edc8');
    logPuzzle('puzzle_monster','monster','calmed_with_generated_ramp');advanceStory('monster');return;
  }
  if(id==='npc'){
    if(storyStep!==4){toast('见证者暂时不愿回答');return}
    logPuzzle('puzzle_npc','npc','question_opened');
    story('见证者的提问','主人，WorldGen 已经给出视觉网格。哪一项还必须由现实证据回答？',[['它已具备真实尺度与摩擦','wrong'],['需要尺度、接触与摩擦校准','calibrate']]);
  }
}
function answerNpc(code){
  logPuzzle('puzzle_answer','npc',code);
  if(code!=='calibrate'){story('见证者摇了摇头','视觉相似不能证明真实物理。再看一次 GLB 来源和场景准入报告。',[['它已具备真实尺度与摩擦','wrong'],['需要尺度、接触与摩擦校准','calibrate']]);return}
  puzzleFlags.npc=true;advanceStory('npc');
}
function makeRobot(data){const groups=new Map(data.links.map(l=>[l.name,new THREE.Group()])),children=new Set(data.joints.map(j=>j.child));for(const l of data.links){const parent=groups.get(l.name);parent.name=l.name;for(const c of l.collisions){let g;if(c.shape==='box')g=new THREE.BoxGeometry(...c.params.size);else if(c.shape==='cylinder')g=new THREE.CylinderGeometry(c.params.radius,c.params.radius,c.params.length,16);else g=new THREE.SphereGeometry(c.params.radius,16,12);const mesh=new THREE.Mesh(g,new THREE.MeshStandardMaterial({color:l.name.includes('wheel')?'#263d44':'#c9e5dc',metalness:.3,roughness:.5,transparent:true,opacity:.9}));if(c.shape==='cylinder')mesh.rotation.x=Math.PI/2;const holder=new THREE.Group();holder.position.set(...c.origin.xyz);holder.rotation.set(...c.origin.rpy,'ZYX');holder.add(mesh);parent.add(holder)}}for(const j of data.joints){const holder=new THREE.Group();holder.position.set(...j.origin.xyz);holder.rotation.set(...j.origin.rpy,'ZYX');holder.add(groups.get(j.child));groups.get(j.parent).add(holder)}const root=data.links.find(l=>!children.has(l.name));const frame=new THREE.Group();frame.rotation.x=-Math.PI/2;frame.add(groups.get(root.name));const outer=new THREE.Group();outer.add(frame);const ring=new THREE.Mesh(new THREE.RingGeometry(.55,.58,40),new THREE.MeshBasicMaterial({color:'#f5c38a',side:THREE.DoubleSide}));ring.rotation.x=-Math.PI/2;ring.position.y=.02;outer.add(ring);return outer}
function resetRobot(){robotBody.setNextKinematicTranslation({x:-11,y:avatarHeight,z:0});robot.position.set(-11,avatarHeight,0);lastPos={x:-11,z:0};travelled=0;trail=[];events=[];contacts=0;tickCount=0;targets=[];$('frames').textContent='0';$('distance').textContent='0.0 m'}
function direction(){let dx=0,dz=0;if(keys.has('w')||keys.has('arrowup'))dx++;if(keys.has('s')||keys.has('arrowdown'))dx--;if(keys.has('a')||keys.has('arrowleft'))dz--;if(keys.has('d')||keys.has('arrowright'))dz++;if(dx||dz){targets=[];return new THREE.Vector2(dx,dz).normalize()}if(targets.length){const p=robotBody.translation(),t=targets[0],v=new THREE.Vector2(t[0]-p.x,t[1]-p.z);if(v.length()<.5){targets.shift();if(!targets.length){patrol=false;$('patrol').textContent='开始自动探索'}return new THREE.Vector2()}return v.normalize()}return new THREE.Vector2()}
function tick(){const dir=direction();if(dir.lengthSq()){controller.computeColliderMovement(robotCollider,{x:dir.x*avatarSpeed,y:0,z:dir.y*avatarSpeed});const d=controller.computedMovement(),p=robotBody.translation();robotBody.setNextKinematicTranslation({x:p.x+d.x,y:p.y+d.y,z:p.z+d.z});if(controller.numComputedCollisions()){contacts+=controller.numComputedCollisions();events.push({time_s:tickCount/60,type:'proxy_collision',count:controller.numComputedCollisions(),position:[p.x,p.z]})}robot.rotation.y=Math.atan2(-dir.y,dir.x)}physics.step();const p=robotBody.translation();robot.position.set(p.x,p.y,p.z);if(lastPos){travelled+=Math.hypot(p.x-lastPos.x,p.z-lastPos.z);lastPos={x:p.x,z:p.z}}for(const v of visuals){if(!v.dynamic)continue;const q=v.body.translation(),r=v.body.rotation();v.mesh.position.set(q.x,q.y,q.z);v.mesh.quaternion.set(r.x,r.y,r.z,r.w)}tickCount++;if(tickCount%6===0){const cube=visuals.find(v=>v.id==='test-cube');const cubeHeight=cube?cube.body.translation().y:null;trail.push({t_s:tickCount/60,position_m:[p.x,p.z,p.y],human_command_direction:[dir.x,dir.y],proxy_contacts_total:contacts,test_cube_height_m:cubeHeight});if(cubeHeight!==null)$('drop-height').textContent=`${cubeHeight.toFixed(2)} m`;$('coords').textContent=`位置 ${p.x.toFixed(1)}, ${p.z.toFixed(1)} m`;$('contacts').textContent=`接触 ${contacts}`;$('frames').textContent=String(trail.length);$('distance').textContent=`${travelled.toFixed(1)} m`;updatePuzzleSignal()}}
function animate(){requestAnimationFrame(animate);if(physics&&robotBody)tick();controls.update();renderer.render(scene,camera)}
function save(name,data,mime){const url=URL.createObjectURL(new Blob([data],{type:mime})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
async function exportMjcf(){const r=await fetch('/api/lab/mjcf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(worldData)}),d=await r.json();if(!r.ok)throw new Error(d.detail||d.error);save('worldstage-physical-world.xml',d.xml,'application/xml');toast('MuJoCo 世界 XML 已生成')}
async function loadPhysicsEvidence(){try{const r=await fetch('/api/lab/physics-evidence');if(!r.ok)throw new Error('未运行');const d=await r.json();$('physics-evidence').textContent=`接触前平均高度差 ${d.mean_abs_difference_pre_contact_m.toFixed(5)} m · S10 动力学 ${d.robot_dynamics}`;const rows=d.samples.filter(v=>[.005,.5,.75,1.2].includes(v.time_s));for(const v of rows){const row=document.createElement('div');row.className='sample-row';row.textContent=`${v.time_s.toFixed(3)} s  ·  ${v.rapier_height_m.toFixed(3)} / ${v.mujoco_height_m.toFixed(3)} m`;row.title='Rapier / MuJoCo 重力箱中心高度';$('physics-samples').append(row)}}catch{$('physics-evidence').textContent='配对结果未运行'}}
async function runSceneGate(){if(!worldData)return;try{const r=await fetch('/api/lab/scene-gate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(worldData)});const report=await r.json();if(!report.schema)throw new Error(report.detail||'准入服务异常');sceneGateReport=report;const unmeasured=report.issues.filter(i=>i.code==='unmeasured_physics').length;const proxy=report.issues.filter(i=>i.code==='collision_proxy_mismatch').length;const engine=report.issues.filter(i=>i.code==='engine_collision_mismatch').length;$('scene-gate-status').textContent=`结构 ${report.structural_status} · MJCF ${report.mjcf_exportable?'可导出':'不可导出'} · 训练 ${report.robot_training_status}`;$('scene-gate-detail').textContent=`${unmeasured} 项物理参数未测 · ${proxy} 项形状待复核 · ${engine} 项跨引擎接触不一致 · NVIDIA SimReady ${report.nvidia_simready_status}`;if(report.structural_status==='PASS'&&storyStep===5)advanceStory('gate');}catch(e){sceneGateReport=null;$('scene-gate-status').textContent=`准入检查失败：${e.message}`}}
async function addPrompt(prompt,mode){const button=document.querySelector('.primary');button.disabled=true;button.querySelector('span').textContent='…';try{const r=await fetch('/api/lab/object',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,mode})}),d=await r.json();if(!r.ok)throw new Error(d.detail||d.error);const p=robotBody.translation(),o=d.object;o.position=[Math.max(-35,Math.min(35,p.x+3)),Math.max(-35,Math.min(35,p.z-3)),Math.max(o.size[2]/2,o.mass_kg>0?3:o.size[2]/2)];worldData.obstacles.push(o);addObstacle(o);generatedKind=o.kind;logPuzzle('object_generated',o.id,`${o.kind}:${d.provenance.mode}`);sceneGateReport=null;$('scene-gate-status').textContent='场景已变化，请复核';$('last-provenance').textContent=`${d.provenance.mode==='nvidia_nemotron'?'NVIDIA Nemotron':'模板'} · ${d.run_id} · ${o.kind} · ${o.mass_kg} kg · ${d.provenance.server_generation_ms} ms`;toast(`${o.name} 已进入世界${o.kind==='ramp'?'；守门兽正在等待你':'；守门兽仍需要斜坡'}`)}catch(e){toast(`生成失败：${e.message}`)}finally{button.disabled=false;button.querySelector('span').textContent='↗'}}
const truthText={experiment:['实验室路线','这片地形可能是为测试机器人失败边界而生成。证据是场景参数、MJCF 和可重放轨迹；真实摩擦仍须测量。'],memory:['记忆路线','这片世界可能来自某张真实照片。必须拿到 WorldGen 原始导出、照片 SHA、尺度和碰撞来源，才可把它称作现实的映射。'],mirror:['分身路线','你或许只是一个数字分身。网页探索留下了候选场景，尚不能证明真实身体也能走过；下一站是同场景 Sim2Sim 与实机反馈。']};
function story(title,copy,choices=[]){$('story-title').textContent=title;$('story-copy').textContent=copy;const box=$('story-choices');box.replaceChildren();for(const [label,code] of choices){const b=document.createElement('button');b.textContent=label;b.addEventListener('click',()=>code==='wrong'||code==='calibrate'?answerNpc(code):chooseTruth(code));box.append(b)}$('story-progress').textContent=`${storyClues.length} / 5 线索${storyTruth?' · 真相路线 '+storyTruth:''}`}
function advanceStory(code){if(storyClues.includes(code))return;storyClues.push(code);if(code==='avatar'&&storyStep===1){storyStep=2;story('第一道记忆：开启宝箱','沿西侧入口的金色信号抵达 (-8, -5)。靠近宝箱按 E，取出失落的能源钥匙。');toast('分身已绑定，寻找宝箱')}else if(code==='chest'&&storyStep===2){storyStep=3;story('第二道记忆：守门兽的条件','宝箱里有一张工程图：制造一段低矮斜坡。用 Nemotron 或模板生成斜坡，去东侧 (6, -8) 安抚守门兽。');toast('获得能源钥匙与斜坡图纸')}else if(code==='monster'&&storyStep===3){storyStep=4;story('第三道记忆：黄栏后的人','守门兽让开了。黄栏后 (2, -17) 藏着一位见证者；绕过障碍找到他，回答关于这个世界的提问。');toast('守门兽交出了第三条信号')}else if(code==='npc'&&storyStep===4){storyStep=5;story('第四道记忆：审查世界','见证者提醒：图像不是摩擦计。点击「复核当前场景」，看它能否进入下一轮仿真。')}else if(code==='gate'&&storyStep===5){storyStep=6;story('三条可能的真相','五条线索都已取得。选择一种解释，再检查尚缺的现实证据。',[['实验室的试验','experiment'],['现实的残影','memory'],['数字分身','mirror']])}else{$('story-progress').textContent=`${storyClues.length} / 5 线索`}}
function chooseTruth(code){const [title,copy]=truthText[code];storyTruth=code;storyStep=7;logPuzzle('truth_selected','ending',code);story(title,copy);toast('真相路线已记录；仍可更换分身并继续探索')}
async function loadAvatar(id){const url=id==='turtlebot3'?'/robots/TurtleBot3-Burger-collision.json':'/robots/S10-collision.json';const data=await fetch(url).then(r=>{if(!r.ok)throw new Error('URDF 载体未找到');return r.json()});avatar=id;urdf=data;avatarHeight=id==='turtlebot3'?.105:.42;avatarSpeed=id==='turtlebot3'?.014:.042;if(robot)scene.remove(robot);robot=makeRobot(data);scene.add(robot);if(robotCollider)physics.removeCollider(robotCollider,true);robotCollider=physics.createCollider(id==='turtlebot3'?RAPIER.ColliderDesc.cuboid(.09,.085,.085).setFriction(.8):RAPIER.ColliderDesc.cuboid(.35,.28,.29).setFriction(.8),robotBody);resetRobot();$('robot-card-name').textContent=data.name;$('robot-meta').textContent=`${data.links.length} 连杆 · ${data.joints.length} 关节 · ${data.total_mass_kg.toFixed(2)} kg`;$('robot-hash').textContent=`URDF SHA ${data.source_sha256.slice(0,16)}…`;$('robot-limit').textContent=id==='turtlebot3'?'ROBOTIS 官方 URDF 的轮式载体；适合平地。台阶、坡道和真实速度限值未在此网页验证。':'DEEPRobotics 官方 URDF 的轮腿载体；网页仅有运动学碰撞代理，真实越障能力待关节仿真验证。';if(worldData)worldData.robot={name:data.name,source_urdf_sha256:data.source_sha256,avatar_mode:'browser_kinematic_proxy'};if(storyStep===1)advanceStory('avatar');toast(`${data.name} 分身已装载`)}
async function init(){await RAPIER.init();const [s,u,h]=await Promise.all([fetch('/api/lab/scenario').then(r=>r.json()),fetch('/robots/S10-collision.json').then(r=>r.json()),fetch('/api/health').then(r=>r.json())]);worldData=s;urdf=u;$('engine').textContent='RAPIER · g = 9.81 m/s²';$('model-status').textContent=h.model_connected?`NVIDIA Nemotron API 已连通 · ${h.model_id}`:h.model_configured?'NVIDIA Nemotron 已配置，等待连通验证':'NVIDIA Nemotron 未连接；可用模板演示';$('robot-meta').textContent=`${u.links.length} 连杆 · ${u.joints.length} 关节 · ${u.total_mass_kg.toFixed(2)} kg`;$('robot-hash').textContent=`URDF SHA ${u.source_sha256.slice(0,16)}…`;decor();physics=new RAPIER.World({x:0,y:-9.81,z:0});const gb=physics.createRigidBody(RAPIER.RigidBodyDesc.fixed().setTranslation(0,-.1,0));physics.createCollider(RAPIER.ColliderDesc.cuboid(40,.1,40).setFriction(.8),gb);s.obstacles.forEach(addObstacle);storyWorld();robot=makeRobot(u);scene.add(robot);robotBody=physics.createRigidBody(RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(-11,.42,0));robotCollider=physics.createCollider(RAPIER.ColliderDesc.cuboid(.35,.28,.29).setFriction(.8),robotBody);controller=physics.createCharacterController(.01);resetRobot();loadWorldGenVisuals();toast('试验仓与三处隐藏线索已加载')}
$('enter-world').addEventListener('click',()=>{$('portal').hidden=true;storyStep=1;story('序章：选择分身','主人，请先确认 S10 轮腿或 TurtleBot3 轮式分身。随后，循着发光线索探索这间失忆的试验仓。')});$('confirm-avatar').addEventListener('click',()=>loadAvatar($('robot-selector').value).catch(e=>toast(e.message)));window.addEventListener('keydown',e=>{if(['TEXTAREA','INPUT','SELECT'].includes(document.activeElement?.tagName))return;if(e.key.toLowerCase()==='e'&&!e.repeat){interactNear();return}keys.add(e.key.toLowerCase())});window.addEventListener('keyup',e=>keys.delete(e.key.toLowerCase()));
renderer.domElement.addEventListener('click',e=>{if(!ground||!robotBody)return;const b=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-b.left)/b.width*2-1,-(e.clientY-b.top)/b.height*2+1);ray.setFromCamera(pointer,camera);const hit=ray.intersectObject(ground)[0];if(hit){targets=[[hit.point.x,hit.point.z]];patrol=false;$('patrol').textContent='开始自动探索';toast('已设置机器人目标点')}});
$('object-form').addEventListener('submit',e=>{e.preventDefault();addPrompt($('object-prompt').value,$('object-mode').value)});document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{$('object-prompt').value=b.dataset.preset;addPrompt(b.dataset.preset,$('object-mode').value)}));$('interact-near').addEventListener('click',interactNear);$('patrol').addEventListener('click',()=>{patrol=!patrol;targets=patrol?(storyStep===2?[[-8,-5]]:storyStep===3?[[-9.5,-4.2],[-9.5,-12],[6,-12],[6,-8]]:storyStep===4?[[9,-11],[8,-17],[2,-17.1]]:[[-8,-5],[6,-8]]):[];$('patrol').textContent=patrol?'停止自动探索':'开始自动探索'});$('reset-robot').addEventListener('click',()=>{patrol=false;$('patrol').textContent='开始自动探索';resetRobot()});$('download-scenario').addEventListener('click',()=>{save('worldstage-physical-scenario.json',JSON.stringify(worldData,null,2),'application/json');toast('场景数据已生成')});$('download-mjcf').addEventListener('click',()=>exportMjcf().catch(e=>toast(e.message)));$('download-trajectory').addEventListener('click',()=>{save('worldstage-proxy-trajectory.json',JSON.stringify({schema:'worldstage.proxy_trajectory.v2',robot:worldData.robot,source_urdf_sha256:urdf.source_sha256,world_gravity_m_s2:worldData.gravity_m_s2,simulation_engine:'rapier3d_browser',robot_control:'human_direction_to_kinematic_collision_proxy',story_clues:storyClues,puzzle_flags:puzzleFlags,truth_route:storyTruth,worldgen_source:worldData.visual_source,frames:trail,events},null,2),'application/json');toast('代理探索轨迹已生成')});
$('check-scene').addEventListener('click',()=>runSceneGate());$('download-scene-gate').addEventListener('click',()=>{if(!sceneGateReport){toast('请先复核当前场景');return}save('worldstage-scene-gate.json',JSON.stringify(sceneGateReport,null,2),'application/json')});
resize();animate();loadPhysicsEvidence();init().then(runSceneGate).catch(e=>{$('engine').textContent='初始化失败';toast(e.message);console.error(e)});
