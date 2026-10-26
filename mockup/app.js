import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { calculate } from './model.mjs';

const host = document.querySelector('#viewport');
const errorBox = document.querySelector('#error');
const widthInput = document.querySelector('#width');
const cutawayInput = document.querySelector('#cutaway');
const showPanelsInput = document.querySelector('#show-panels');
const dynamic = new THREE.Group();
let renderer;
let camera;
let controls;
let scene;
let width = 500;

const colors = {
  panel: 0x81c3ad,
  hinge: 0xe49e68,
  rod: 0xb9e786,
  sleeve: 0x9ba8a0,
  support: 0x62746a,
  dark: 0x17211d,
};

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = `Không thể hiển thị mô hình 3D: ${message}`;
}

window.addEventListener('unhandledrejection', event => showError(event.reason?.message || 'Lỗi khởi tạo mô hình.'));

function material(color, options = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.64, metalness: 0.04, ...options });
}

function dispose(group) {
  group.traverse(object => {
    if (object.geometry) object.geometry.dispose();
    if (object.material) {
      const materials = Array.isArray(object.material) ? object.material : [object.material];
      materials.forEach(item => item.dispose());
    }
  });
  group.clear();
}

function cylinderAlongX(group, radius, length, x, y, z, mat, segments = 40) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, segments), mat);
  mesh.rotation.z = Math.PI / 2;
  mesh.position.set(x, y, z);
  group.add(mesh);
  return mesh;
}

function addThread(group, start, length, y, z, radius, pitch, mat, tubeRadius = 0.6, phase = 0) {
  const points = [];
  const samples = Math.ceil(length / pitch * 18);
  for (let i = 0; i <= samples; i++) {
    const t = i / samples;
    const angle = -t * length / pitch * Math.PI * 2 + phase;
    points.push(new THREE.Vector3(start + length * t, y + radius * Math.cos(angle), z + radius * Math.sin(angle)));
  }
  const curve = new THREE.CatmullRomCurve3(points, false, 'centripetal');
  const mesh = new THREE.Mesh(new THREE.TubeGeometry(curve, samples, tubeRadius, 5, false), mat);
  group.add(mesh);
}

function addSupport(group, x, y, z, side) {
  const mat = material(colors.support);
  const base = new THREE.Mesh(new THREE.BoxGeometry(21, 28, 20), mat);
  base.position.set(x, y, z);
  group.add(base);
  const cheek = new THREE.Mesh(new THREE.BoxGeometry(8, 40, 30), material(colors.support, { roughness: 0.8 }));
  cheek.position.set(x, y, z + side * 13);
  group.add(cheek);
  const bearing = new THREE.Mesh(new THREE.TorusGeometry(13, 2.2, 8, 40), material(colors.dark));
  bearing.rotation.y = Math.PI / 2;
  bearing.position.set(x, y, z);
  group.add(bearing);
}

function addRightRing(group, model, cutaway) {
  const ring = model.rightRing;
  const cavity = ring.cavityProfile;
  const profile = [
    new THREE.Vector2(cavity[0][1], cavity[0][0]),
    new THREE.Vector2(ring.outerRadius, ring.start),
    new THREE.Vector2(ring.outerRadius, ring.end),
    ...cavity.slice().reverse().map(([x, radius]) => new THREE.Vector2(radius, x)),
  ];
  const shell = new THREE.Mesh(new THREE.LatheGeometry(profile, 64,
    cutaway ? 0.45 : 0, cutaway ? Math.PI * 1.55 : Math.PI * 2), material(colors.support, {
    transparent: cutaway, opacity: cutaway ? 0.48 : 1, side: THREE.DoubleSide,
  }));
  shell.rotation.z = -Math.PI / 2;
  shell.position.set(ring.axisX, ring.axisY, ring.axisZ);
  group.add(shell);

  const web = new THREE.Mesh(new THREE.BoxGeometry(6, 16, 12), material(0x6f8778));
  web.position.set(ring.axisX + 7, ring.axisY, -10);
  group.add(web);
  const endPlate = new THREE.Mesh(new THREE.BoxGeometry(5, 200, 4), material(0x718579));
  endPlate.position.set(model.width - 2.5, ring.axisY, -2);
  group.add(endPlate);
}

function addRotor(group, model, cutaway) {
  const rotor = model.rotor;
  const rotorGroup = new THREE.Group();
  rotorGroup.position.set(rotor.start, model.height / 2, model.rod.z);
  rotorGroup.rotation.x = model.turnsFrom200 * Math.PI * 2;
  group.add(rotorGroup);
  const mat = material(colors.sleeve, {
    transparent: cutaway, opacity: cutaway ? 0.42 : 1,
    side: THREE.DoubleSide, depthWrite: !cutaway,
  });
  const slices = rotor.outerProfile.slice(0, -1).map(([start, r1], i) => {
    const [end, r2] = rotor.outerProfile[i + 1];
    return [start, end, r1, r2];
  });
  for (const [start, end, r1, r2] of slices) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(r1, r2, end - start, 48, 1, true,
      cutaway ? 0.45 : 0, cutaway ? Math.PI * 1.55 : Math.PI * 2), mat);
    mesh.rotation.z = Math.PI / 2;
    mesh.position.x = (start + end) / 2;
    rotorGroup.add(mesh);
  }
  // Groove-crest radius after thread_offset=-0.25. This is not the full tooth profile.
  addThread(rotorGroup, 0, rotor.threadLength, 0, 0, 10.5, 4,
    material(0x79867c, { roughness: 0.48, transparent: cutaway, opacity: cutaway ? 0.85 : 1 }), 0.65);
  if (cutaway) {
    const shell = new THREE.Mesh(new THREE.CylinderGeometry(rotor.innerBoreRadius, rotor.innerBoreRadius,
      130, 48, 1, true, 0.45, Math.PI * 1.55),
      material(0x79867c, { side: THREE.DoubleSide, transparent: true, opacity: 0.75 }));
    shell.rotation.z = Math.PI / 2;
    shell.position.x = 65;
    rotorGroup.add(shell);
  }
}

function addEndBridge(group, axis, bearingX, y, z) {
  const dx = bearingX - axis.x;
  const dz = z - axis.z;
  const length = Math.hypot(dx, dz);
  const arm = new THREE.Mesh(new THREE.BoxGeometry(length, 15, 8), material(0x6f8778));
  arm.position.set((axis.x + bearingX) / 2, y, (axis.z + z) / 2);
  arm.rotation.y = -Math.atan2(dz, dx);
  group.add(arm);
  const boss = new THREE.Mesh(new THREE.CylinderGeometry(7, 7, 13, 24), material(0x6f8778));
  boss.position.set(axis.x, y, axis.z);
  group.add(boss);
  const bore = new THREE.Mesh(new THREE.CylinderGeometry(2.8, 2.8, 14, 16), material(0x213029));
  bore.position.copy(boss.position);
  group.add(bore);
}

function buildModel() {
  dispose(dynamic);
  const model = calculate(width);
  const panelGroup = new THREE.Group();
  const panelMat = material(colors.panel, { roughness: 0.72, side: THREE.DoubleSide });
  if (showPanelsInput.checked) {
    for (let i = 0; i < model.axes.length - 1; i++) {
      const a = model.axes[i];
      const b = model.axes[i + 1];
      const centerX = (a.x + b.x) / 2;
      const centerZ = (a.z + b.z) / 2;
      const angle = -Math.atan2(b.z - a.z, b.x - a.x);
      const slab = new THREE.Mesh(new THREE.BoxGeometry(model.panelLength, model.height, 3.2), panelMat);
      slab.position.set(centerX, model.height / 2, centerZ);
      slab.rotation.y = angle;
      panelGroup.add(slab);
      const edge = new THREE.Mesh(new THREE.BoxGeometry(2.8, model.height + 3, 5), material(0x6ca58f));
      edge.position.set(a.x, model.height / 2, a.z);
      panelGroup.add(edge);
    }
  }
  dynamic.add(panelGroup);

  const hingeMat = material(colors.hinge);
  for (let i = 1; i < model.axes.length - 1; i++) {
    const axis = model.axes[i];
    for (const y of [24, 100, 176]) {
      const barrel = new THREE.Mesh(new THREE.CylinderGeometry(model.hingeBarrelRadius, model.hingeBarrelRadius, 18, 20), hingeMat);
      barrel.position.set(axis.x, y, axis.z);
      dynamic.add(barrel);
      const pin = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 20, 12), material(0x44352b));
      pin.position.set(axis.x, y, axis.z);
      dynamic.add(pin);
    }
  }
  for (const index of [0, model.axes.length - 1]) {
    const axis = model.axes[index];
    const pivot = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, model.height, 16), material(0xb4c7ba));
    pivot.position.set(axis.x, model.height / 2, axis.z);
    dynamic.add(pivot);
  }

  const rodY = model.height / 2;
  const rodZ = model.rod.z;
  const rodCenter = (model.rod.start + model.rod.end) / 2;
  const threadMat = material(colors.rod, { roughness: 0.4, metalness: 0.08 });
  cylinderAlongX(dynamic, 9, model.rod.length, rodCenter, rodY, rodZ, material(0x82955e), 40);
  addThread(dynamic, model.rod.start, model.rod.length, rodY, rodZ, 9.4, 4, threadMat, 0.6);
  const extension = model.extension;
  const shankLength = extension.tipStart - extension.start;
  cylinderAlongX(dynamic, extension.radius, shankLength, extension.start + shankLength / 2, rodY, rodZ, material(0xc4b496), 40);
  addThread(dynamic, extension.tipStart, extension.tipLength, rodY, rodZ, 9.4, 4, threadMat, 0.6);

  addRotor(dynamic, model, cutawayInput.checked);

  addSupport(dynamic, model.axes[0].x + 11, rodY, rodZ, -1);
  addEndBridge(dynamic, model.axes[0], model.axes[0].x + 11, rodY, rodZ);
  addRightRing(dynamic, model, cutawayInput.checked);

  document.querySelector('#width-value').innerHTML = `${model.width} <small>mm</small>`;
  document.querySelector('#overlap').innerHTML = `${model.overlap} <small>mm</small>`;
  document.querySelector('#fold-depth').innerHTML = `${model.foldDepth.toFixed(1)} <small>mm</small>`;
  const turns = model.turnsFrom500;
  const turnsText = turns > 0 ? `+${turns}` : `${turns}`;
  document.querySelector('#turns').innerHTML = `${turnsText} <small>vòng</small>`;
  const percent = (model.width - 430) / 70 * 100;
  widthInput.style.background = `linear-gradient(to right, var(--green) 0%, var(--green) ${percent}%, #46534d ${percent}%, #46534d 100%)`;
}

function lookAt(widthAt = width, mode = 'iso') {
  const target = new THREE.Vector3(widthAt / 2, 100, 0);
  controls.target.copy(target);
  const distance = Math.max(310, widthAt * 2.1);
  if (mode === 'front') camera.position.set(widthAt / 2, 130, distance);
  else if (mode === 'top') camera.position.set(widthAt / 2, distance, 0.01);
  else camera.position.set(widthAt / 2 + distance * 0.72, 100 + distance * 0.55, distance * 0.8);
  camera.up.set(0, mode === 'top' ? 0 : 1, mode === 'top' ? -1 : 0);
  camera.lookAt(target);
  controls.update();
  document.querySelector('#view-label').textContent = mode === 'front' ? 'MẶT TRƯỚC' : mode === 'top' ? 'NHÌN TRÊN' : 'GÓC PHỐI CẢNH';
  document.querySelectorAll('[data-view]').forEach(button => button.classList.toggle('selected', button.dataset.view === mode));
}

function init() {
  try {
    scene = new THREE.Scene();
    scene.background = new THREE.Color('#18221f');
    scene.add(new THREE.HemisphereLight(0xe0eee5, 0x29352f, 2.2));
    const key = new THREE.DirectionalLight(0xfff1d8, 2.8);
    key.position.set(-150, 300, 320);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x93b9a3, 1.4);
    rim.position.set(270, 160, -240);
    scene.add(rim);

    const grid = new THREE.GridHelper(800, 32, 0x45574d, 0x2b3933);
    grid.position.y = -2;
    grid.material.transparent = true;
    grid.material.opacity = 0.42;
    scene.add(grid);
    scene.add(dynamic);
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;
    host.appendChild(renderer.domElement);
    camera = new THREE.PerspectiveCamera(34, host.clientWidth / host.clientHeight, 1, 4000);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.minDistance = 190;
    controls.maxDistance = 1800;
    controls.maxPolarAngle = Math.PI * 0.49;
    lookAt(500, 'iso');
    buildModel();

    const resize = new ResizeObserver(() => {
      const { clientWidth, clientHeight } = host;
      if (!clientWidth || !clientHeight) return;
      camera.aspect = clientWidth / clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(clientWidth, clientHeight);
    });
    resize.observe(host);
    renderer.setAnimationLoop(() => {
      controls.update();
      renderer.render(scene, camera);
    });
  } catch (error) {
    showError(error.message || 'Trình duyệt không hỗ trợ WebGL.');
  }
}

widthInput.addEventListener('input', () => {
  width = Number(widthInput.value);
  document.querySelectorAll('[data-width]').forEach(button => button.classList.toggle('selected', Number(button.dataset.width) === width));
  buildModel();
});
document.querySelectorAll('[data-width]').forEach(button => button.addEventListener('click', () => {
  width = Number(button.dataset.width);
  widthInput.value = width;
  widthInput.dispatchEvent(new Event('input', { bubbles: true }));
}));
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => lookAt(width, button.dataset.view)));
showPanelsInput.addEventListener('change', buildModel);
cutawayInput.addEventListener('change', buildModel);

init();
