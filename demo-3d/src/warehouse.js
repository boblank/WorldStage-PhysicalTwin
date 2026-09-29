import * as THREE from 'three';

// Authored enclosure around the actual WorldGen exports. Its dimensions and
// materials are design assumptions, not a reconstruction of the source photo.
export function buildWarehouse(scene){
  const concrete=document.createElement('canvas');concrete.width=concrete.height=512;
  const ctx=concrete.getContext('2d');ctx.fillStyle='#737b78';ctx.fillRect(0,0,512,512);
  let seed=290929;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
  for(let i=0;i<21000;i++){const shade=45+Math.floor(random()*100);ctx.fillStyle=`rgba(${shade},${shade+4},${shade+2},${random()*.09})`;ctx.fillRect(random()*512,random()*512,1+random()*4,1+random()*4)}
  ctx.strokeStyle='#39474480';ctx.lineWidth=2;for(let x=0;x<=512;x+=128){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,512);ctx.stroke();ctx.beginPath();ctx.moveTo(0,x);ctx.lineTo(512,x);ctx.stroke()}
  const floorTexture=new THREE.CanvasTexture(concrete);floorTexture.wrapS=floorTexture.wrapT=THREE.RepeatWrapping;floorTexture.repeat.set(10,10);floorTexture.colorSpace=THREE.SRGBColorSpace;
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(80,80),new THREE.MeshStandardMaterial({map:floorTexture,roughness:.98,metalness:0}));floor.rotation.x=-Math.PI/2;floor.position.y=-.035;floor.receiveShadow=true;scene.add(floor);
  const wallMat=new THREE.MeshStandardMaterial({color:'#9aa19b',roughness:.92});
  const steel=new THREE.MeshStandardMaterial({color:'#314047',metalness:.72,roughness:.42});
  const yellow=new THREE.MeshStandardMaterial({color:'#ddb359',metalness:.35,roughness:.5});
  const dim=new THREE.MeshStandardMaterial({color:'#28363a',metalness:.3,roughness:.8});
  const add=(geometry,material,x,y,z,cast=true)=>{const mesh=new THREE.Mesh(geometry,material);mesh.position.set(x,y,z);mesh.castShadow=cast;mesh.receiveShadow=true;scene.add(mesh);return mesh};
  // Back and side walls frame the arena; the camera-facing wall is omitted.
  add(new THREE.BoxGeometry(40,7,.32),wallMat,0,3.5,-23);
  add(new THREE.BoxGeometry(.32,7,34),wallMat,-19.8,3.5,-6);
  add(new THREE.BoxGeometry(.32,7,34),wallMat,19.8,3.5,-6);
  for(const x of [-18,-9,0,9,18]){
    add(new THREE.BoxGeometry(.22,7,.28),steel,x,3.5,-22.65);
    const lamp=add(new THREE.BoxGeometry(2.5,.08,.34),new THREE.MeshBasicMaterial({color:'#f4eed7'}),x,6.45,-20.5,false);
    lamp.rotation.x=-.28;
    const light=new THREE.PointLight('#fff0d0',16,14,2);light.position.set(x,5.8,-19);scene.add(light);
  }
  for(const z of [-19,-11,-3,5]){
    for(const x of [-19.4,19.4])add(new THREE.BoxGeometry(.22,7,.27),steel,x,3.5,z);
  }
  for(const z of [-19.5,-14.5,-9.5,-4.5,.5,5.5]){
    add(new THREE.BoxGeometry(39,.045,.04),dim,0,.011,z,false);
  }
  for(const x of [-14,-7,0,7,14])add(new THREE.BoxGeometry(.035,.045,33),dim,x,.012,-6,false);
  // Zones are legible in the world and useful in the exported behaviour log.
  for(const [x,z,label] of [[-11,0,'ENTRY 01'],[-8,-5,'MEMORY'],[6,-8,'TEST 02'],[2,-16,'ARCHIVE']]){
    const c=document.createElement('canvas');c.width=512;c.height=96;const t=c.getContext('2d');t.fillStyle='#142b2c';t.fillRect(0,0,512,96);t.fillStyle='#f3d58c';t.font='bold 58px sans-serif';t.textAlign='center';t.fillText(label,256,68);
    const map=new THREE.CanvasTexture(c);map.colorSpace=THREE.SRGBColorSpace;
    const board=add(new THREE.PlaneGeometry(3.3,.62),new THREE.MeshBasicMaterial({map,transparent:true,side:THREE.DoubleSide}),x,2.9,z-1.5,false);board.rotation.y=0;
  }
  for(const [x,z] of [[-14,-14],[12,-16],[14,-2],[-15,6]]){
    add(new THREE.BoxGeometry(1.6,.95,1.2),new THREE.MeshStandardMaterial({color:'#6b5b45',roughness:.9}),x,.48,z);
    for(const dx of [-.65,.65])add(new THREE.BoxGeometry(.055,1,.055),steel,x+dx,.5,z+.5);
  }
  for(let i=0;i<4;i++){
    const z=-18+i*6;
    add(new THREE.CylinderGeometry(.09,.09,1.5,10),yellow,17.8,.75,z);
    add(new THREE.BoxGeometry(.08,.08,6),yellow,17.8,1.42,z+3,false);
  }
  for(const x of [-16,16]){
    const bulb=new THREE.PointLight('#b9e4e1',12,12,2);bulb.position.set(x,4,0);scene.add(bulb);
  }
  const haze=new THREE.FogExp2('#53605e',.016);scene.fog=haze;
  return floor;
}
