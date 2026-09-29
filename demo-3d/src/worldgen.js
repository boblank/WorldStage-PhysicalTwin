import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import './worldgen.css';

const root = '/worldgen/robot-test-arena/';
const viewport = document.getElementById('viewer');
const status = document.getElementById('load-status');
const list = document.getElementById('asset-list');
const scene = new THREE.Scene();
scene.background = new THREE.Color('#102630');
scene.fog = new THREE.Fog('#102630', 20, 45);
const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 100);
camera.position.set(6, 4.5, 7);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.45;
viewport.appendChild(renderer.domElement);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 0.2, -0.5);
controls.maxPolarAngle = Math.PI * 0.48;
controls.minDistance = 2;
controls.maxDistance = 35;
scene.add(new THREE.HemisphereLight('#e8f6fa', '#243039', 2.3));
const sun = new THREE.DirectionalLight('#fff3df', 2.8);
sun.position.set(-5, 9, 7);
scene.add(sun);
const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), new THREE.MeshStandardMaterial({ color: '#5f7279', roughness: 1 }));
floor.rotation.x = -Math.PI / 2;
floor.position.y = -0.018;
scene.add(floor);
const grid = new THREE.GridHelper(20, 20, '#99bcc0', '#658087');
grid.material.transparent = true;
grid.material.opacity = 0.27;
scene.add(grid);
const proxyGroup = new THREE.Group();
proxyGroup.visible = false;
scene.add(proxyGroup);
const loader = new GLTFLoader();
const models = new Map();

function resize() {
  const w = viewport.clientWidth, h = viewport.clientHeight;
  if (!w || !h) return;
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  renderer.setSize(w, h);
}
new ResizeObserver(resize).observe(viewport);
function animate() { requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }
animate();

function focus(id) {
  const model = models.get(id);
  if (!model) return;
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(3, 2.5, 4));
}

async function init() {
  const [manifest, physical] = await Promise.all([
    fetch(root + 'manifest.json').then(r => r.json()),
    fetch(root + 'scene.json').then(r => r.json()),
  ]);
  const byId = new Map(physical.obstacles.map(item => [item.id, item]));
  let loaded = 0;
  for (const asset of manifest.assets) {
    const row = document.createElement('button');
    row.className = 'asset';
    row.textContent = `${String(loaded + 1).padStart(2, '0')}  ${asset.name}`;
    row.addEventListener('click', () => focus(asset.id));
    list.appendChild(row);
    const gltf = await loader.loadAsync(root + asset.glb);
    const m = asset.transform.flat();
    gltf.scene.applyMatrix4(new THREE.Matrix4().set(...m));
    // Ground each mesh for display. The export's world origin and metric scale
    // are not verified, so this is visual normalization only.
    const box = new THREE.Box3().setFromObject(gltf.scene);
    gltf.scene.position.y -= box.min.y;
    scene.add(gltf.scene);
    models.set(asset.id, gltf.scene);
    const proxy = byId.get(asset.id);
    if (proxy) {
      const [width, depth, height] = proxy.size;
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        new THREE.MeshBasicMaterial({ color: '#ffc47d', transparent: true, opacity: 0.12, depthWrite: false }),
      );
      mesh.position.set(proxy.position[0], height / 2, proxy.position[1]);
      proxyGroup.add(mesh);
      const edges = new THREE.LineSegments(new THREE.EdgesGeometry(mesh.geometry), new THREE.LineBasicMaterial({ color: '#ffc47d' }));
      edges.position.copy(mesh.position);
      proxyGroup.add(edges);
    }
    loaded++;
    status.textContent = `${loaded} / ${manifest.assets.length} GLB 已加载`;
  }
}

document.getElementById('toggle-proxies').addEventListener('click', e => {
  proxyGroup.visible = !proxyGroup.visible;
  e.currentTarget.textContent = proxyGroup.visible ? '隐藏估计碰撞包围盒' : '显示估计碰撞包围盒';
});
document.getElementById('reset-camera').addEventListener('click', () => {
  controls.target.set(0, 0.2, -0.5);
  camera.position.set(6, 4.5, 7);
});
init().catch(error => { status.textContent = `加载失败：${error.message}`; console.error(error); });
