import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { EnvironmentConfig, SimulationFrame } from '../types/benchmark';

interface DonerSceneProps {
  frame: SimulationFrame;
  environment: EnvironmentConfig;
}

interface SceneRefs {
  renderer: THREE.WebGLRenderer;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  doner: THREE.Group;
  knife: THREE.Group;
  cutGroup: THREE.Group;
  slice: THREE.Mesh;
  flameGroup: THREE.Group;
  fireLight: THREE.PointLight;
  animationId: number;
  textures: THREE.Texture[];
}

export function DonerScene({ frame, environment }: DonerSceneProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<SceneRefs | null>(null);
  const frameRef = useRef(frame);

  useEffect(() => {
    frameRef.current = frame;
  }, [frame]);

  useEffect(() => {
    if (!hostRef.current) return;

    const host = hostRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color('#111416');
    scene.fog = new THREE.Fog('#111416', 18, 34);

    const camera = new THREE.PerspectiveCamera(32, host.clientWidth / host.clientHeight, 0.1, 100);
    camera.position.set(-0.8, 4.7, 15.5);
    camera.lookAt(0.25, 1.15, 0);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: false,
      preserveDrawingBuffer: true
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    host.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight('#ffd8a8', '#273341', 1.15));

    const key = new THREE.DirectionalLight('#ffe1a8', 2.2);
    key.position.set(-4, 8, 7);
    key.castShadow = true;
    scene.add(key);

    const fireLight = new THREE.PointLight('#ff8b32', 3.2, 16);
    fireLight.position.set(3.0, 1.25, 0.45);
    scene.add(fireLight);

    const donerTextures = createDonerTextures();
    const sliceTexture = createSliceTexture();
    const doner = buildDoner(environment, donerTextures);
    scene.add(doner);

    const skewer = new THREE.Mesh(
      new THREE.CylinderGeometry(0.045, 0.045, 8.9, 20),
      new THREE.MeshStandardMaterial({ color: '#d9e1e6', metalness: 0.75, roughness: 0.24 })
    );
    skewer.position.y = 1.15;
    skewer.castShadow = true;
    scene.add(skewer);

    const tray = new THREE.Mesh(
      new THREE.CylinderGeometry(2.25, 2.45, 0.12, 72),
      new THREE.MeshStandardMaterial({ color: '#5d6770', metalness: 0.8, roughness: 0.32 })
    );
    tray.position.y = -2.3;
    tray.receiveShadow = true;
    scene.add(tray);

    const burner = new THREE.Group();
    const backplate = new THREE.Mesh(
      new THREE.BoxGeometry(2.1, 5.6, 0.22),
      new THREE.MeshStandardMaterial({
        color: '#273038',
        metalness: 0.45,
        roughness: 0.38,
        emissive: '#271006',
        emissiveIntensity: 0.3
      })
    );
    backplate.position.set(3.25, 1.1, -0.6);
    burner.add(backplate);

    for (let i = 0; i < 4; i += 1) {
      const rail = new THREE.Mesh(
        new THREE.BoxGeometry(1.65, 0.08, 0.08),
        new THREE.MeshStandardMaterial({
          color: '#ff6d23',
          emissive: '#ff5b15',
          emissiveIntensity: 1.7,
          roughness: 0.5
        })
      );
      rail.position.set(3.2, -0.8 + i * 1.08, -0.43);
      burner.add(rail);
    }
    scene.add(burner);

    const flameGroup = buildFlames();
    scene.add(flameGroup);

    const knife = buildKnife();
    scene.add(knife);

    const cutGroup = new THREE.Group();
    scene.add(cutGroup);

    const slice = new THREE.Mesh(
      new THREE.BoxGeometry(1.2, 0.045, 0.55, 4, 1, 4),
      new THREE.MeshStandardMaterial({
        map: sliceTexture,
        color: '#f0b174',
        emissive: '#3c1404',
        emissiveIntensity: 0.2,
        roughness: 0.86
      })
    );
    slice.visible = false;
    slice.castShadow = true;
    scene.add(slice);

    let animationId = 0;
    const animate = () => {
      const now = performance.now() / 1000;
      const activeFrame = frameRef.current;
      doner.rotation.y = activeFrame.rotation_angle + Math.sin(now * 1.8) * 0.015;
      flameGroup.children.forEach((child, index) => {
        child.scale.y = 0.8 + Math.sin(now * 7.0 + index * 1.7) * 0.18;
        child.scale.x = 0.8 + Math.cos(now * 5.5 + index) * 0.08;
        child.position.y = -1.0 + (index % 5) * 0.78 + Math.sin(now * 8 + index) * 0.035;
      });
      fireLight.intensity = 2.75 + Math.sin(now * 9.0) * 0.45;
      renderer.render(scene, camera);
      animationId = window.requestAnimationFrame(animate);
      if (sceneRef.current) sceneRef.current.animationId = animationId;
    };

    sceneRef.current = {
      renderer,
      scene,
      camera,
      doner,
      knife,
      cutGroup,
      slice,
      flameGroup,
      fireLight,
      animationId,
      textures: [...donerTextures, sliceTexture]
    };

    const resize = () => {
      if (!host.clientWidth || !host.clientHeight) return;
      camera.aspect = host.clientWidth / host.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(host.clientWidth, host.clientHeight);
    };
    window.addEventListener('resize', resize);
    resize();
    updateSceneFromFrame(sceneRef.current, frameRef.current);
    animate();

    return () => {
      window.removeEventListener('resize', resize);
      window.cancelAnimationFrame(animationId);
      host.removeChild(renderer.domElement);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          if (Array.isArray(object.material)) {
            object.material.forEach((material) => material.dispose());
          } else {
            object.material.dispose();
          }
        }
      });
      sceneRef.current?.textures.forEach((texture) => texture.dispose());
      renderer.dispose();
    };
  }, [environment.cone_height, environment.cone_radius_bottom, environment.cone_radius_top]);

  useEffect(() => {
    const refs = sceneRef.current;
    if (!refs) return;
    updateSceneFromFrame(refs, frame);
  }, [frame]);

  return <div className="scene-host" ref={hostRef} />;
}

function buildDoner(environment: EnvironmentConfig, textures: THREE.Texture[]) {
  const doner = new THREE.Group();
  const height = environment.cone_height / 7;
  const [colorMap, roughnessMap, bumpMap] = textures;

  const body = new THREE.Mesh(
    new THREE.CylinderGeometry(
      environment.cone_radius_bottom / 7,
      environment.cone_radius_top / 7,
      height,
      96,
      28
    ),
    new THREE.MeshStandardMaterial({
      map: colorMap,
      roughnessMap,
      bumpMap,
      bumpScale: 0.085,
      color: '#d18a52',
      roughness: 0.92,
      metalness: 0.01
    })
  );
  body.position.y = 1.15;
  body.castShadow = true;
  body.receiveShadow = true;
  doner.add(body);

  const layerColors = ['#c07443', '#8d4329', '#d29461', '#6f2f21'];
  for (let i = 0; i < 18; i += 1) {
    const location = i / 17;
    const radius = THREE.MathUtils.lerp(
      environment.cone_radius_bottom / 7,
      environment.cone_radius_top / 7,
      location
    );
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius * (0.94 + Math.sin(i * 1.8) * 0.025), 0.012, 7, 96),
      new THREE.MeshStandardMaterial({
        color: layerColors[i % layerColors.length],
        roughness: 0.95
      })
    );
    ring.position.y = 1.15 + height / 2 - location * height;
    ring.rotation.x = Math.PI / 2;
    doner.add(ring);
  }

  const charMaterial = new THREE.MeshBasicMaterial({ color: '#2a130d', transparent: true, opacity: 0.55 });
  for (let i = 0; i < 34; i += 1) {
    const location = (i * 0.618) % 1;
    const angle = i * 2.37;
    const radius = THREE.MathUtils.lerp(
      environment.cone_radius_bottom / 7,
      environment.cone_radius_top / 7,
      location
    );
    const mark = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.42 + (i % 4) * 0.08, 0.018), charMaterial);
    const y = 1.15 + height / 2 - location * height;
    mark.position.set(Math.sin(angle) * radius * 1.01, y, Math.cos(angle) * radius * 1.01);
    mark.lookAt(0, y, 0);
    doner.add(mark);
  }

  return doner;
}

function createDonerTextures(): [THREE.CanvasTexture, THREE.CanvasTexture, THREE.CanvasTexture] {
  const size = 512;
  const colorCanvas = document.createElement('canvas');
  colorCanvas.width = size;
  colorCanvas.height = size;
  const color = colorCanvas.getContext('2d');
  if (!color) throw new Error('Could not create texture context');

  const base = color.createLinearGradient(0, 0, size, size);
  base.addColorStop(0, '#9b4b2e');
  base.addColorStop(0.35, '#d4874c');
  base.addColorStop(0.7, '#7b3425');
  base.addColorStop(1, '#e2a264');
  color.fillStyle = base;
  color.fillRect(0, 0, size, size);

  for (let y = 0; y < size; y += 14) {
    color.fillStyle = y % 42 === 0 ? 'rgba(255, 196, 124, 0.24)' : 'rgba(58, 22, 12, 0.2)';
    color.fillRect(0, y + Math.sin(y * 0.07) * 3, size, 4 + (y % 5));
  }

  for (let i = 0; i < 170; i += 1) {
    const x = seededNoise(i * 19.3) * size;
    const y = seededNoise(i * 7.9 + 11) * size;
    const w = 8 + seededNoise(i + 3) * 38;
    const h = 1 + seededNoise(i + 9) * 5;
    color.fillStyle = i % 4 === 0 ? 'rgba(42, 13, 7, 0.52)' : 'rgba(255, 218, 153, 0.18)';
    color.save();
    color.translate(x, y);
    color.rotate((seededNoise(i * 2.1) - 0.5) * 0.8);
    color.fillRect(-w / 2, -h / 2, w, h);
    color.restore();
  }

  const roughCanvas = document.createElement('canvas');
  roughCanvas.width = size;
  roughCanvas.height = size;
  const rough = roughCanvas.getContext('2d');
  if (!rough) throw new Error('Could not create roughness texture context');
  rough.fillStyle = '#dadada';
  rough.fillRect(0, 0, size, size);
  for (let i = 0; i < 220; i += 1) {
    rough.fillStyle = i % 3 === 0 ? 'rgba(255,255,255,0.35)' : 'rgba(95,95,95,0.26)';
    rough.beginPath();
    rough.ellipse(
      seededNoise(i * 3.1) * size,
      seededNoise(i * 5.7) * size,
      3 + seededNoise(i) * 18,
      1 + seededNoise(i + 2) * 8,
      seededNoise(i + 4) * Math.PI,
      0,
      Math.PI * 2
    );
    rough.fill();
  }

  const bumpCanvas = document.createElement('canvas');
  bumpCanvas.width = size;
  bumpCanvas.height = size;
  const bump = bumpCanvas.getContext('2d');
  if (!bump) throw new Error('Could not create bump texture context');
  bump.fillStyle = '#808080';
  bump.fillRect(0, 0, size, size);
  for (let y = 0; y < size; y += 8) {
    const shade = 105 + (y % 24) * 4;
    bump.fillStyle = `rgb(${shade}, ${shade}, ${shade})`;
    bump.fillRect(0, y + Math.sin(y * 0.12) * 4, size, 2);
  }

  return [toTexture(colorCanvas), toTexture(roughCanvas), toTexture(bumpCanvas)];
}

function createSliceTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 128;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Could not create slice texture context');
  context.fillStyle = '#d98b53';
  context.fillRect(0, 0, canvas.width, canvas.height);
  for (let y = 8; y < canvas.height; y += 13) {
    context.strokeStyle = y % 2 === 0 ? 'rgba(255,220,160,0.45)' : 'rgba(92,36,18,0.35)';
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(0, y);
    for (let x = 0; x <= canvas.width; x += 16) {
      context.lineTo(x, y + Math.sin(x * 0.08 + y) * 4);
    }
    context.stroke();
  }
  return toTexture(canvas);
}

function toTexture(canvas: HTMLCanvasElement) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(1.8, 2.6);
  texture.anisotropy = 8;
  texture.needsUpdate = true;
  return texture;
}

function seededNoise(value: number) {
  const raw = Math.sin(value * 12.9898 + 78.233) * 43758.5453;
  return raw - Math.floor(raw);
}

function buildFlames() {
  const group = new THREE.Group();
  const colors = ['#ff7a1f', '#ffb02e', '#fff0a8'];
  for (let row = 0; row < 6; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const flame = new THREE.Mesh(
        new THREE.ConeGeometry(0.18 - col * 0.035, 0.9 - col * 0.14, 8, 1, true),
        new THREE.MeshBasicMaterial({
          color: colors[col],
          transparent: true,
          opacity: 0.62 - col * 0.1,
          blending: THREE.AdditiveBlending,
          depthWrite: false
        })
      );
      flame.position.set(2.82 + col * 0.08, -1.0 + row * 0.78, -0.12 + col * 0.06);
      flame.rotation.z = -Math.PI / 2;
      group.add(flame);
    }
  }
  return group;
}

function buildKnife() {
  const group = new THREE.Group();
  const bladeShape = new THREE.Shape();
  bladeShape.moveTo(-0.12, -1.45);
  bladeShape.lineTo(0.18, -1.18);
  bladeShape.lineTo(0.12, 1.28);
  bladeShape.lineTo(-0.16, 1.45);
  bladeShape.lineTo(-0.12, -1.45);
  const blade = new THREE.Mesh(
    new THREE.ExtrudeGeometry(bladeShape, { depth: 0.045, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012 }),
    new THREE.MeshStandardMaterial({ color: '#dfe7ef', metalness: 0.86, roughness: 0.17 })
  );
  blade.castShadow = true;
  group.add(blade);
  const handle = new THREE.Mesh(
    new THREE.BoxGeometry(0.28, 0.9, 0.12),
    new THREE.MeshStandardMaterial({ color: '#202326', roughness: 0.55 })
  );
  handle.position.y = -1.55;
  group.add(handle);
  return group;
}

// Physical control maxes (must match backend AgentAction bounds) used to map the
// real-unit knife state (mm, cm/s) back to 0-1 for rendering.
const CUT_DEPTH_MAX_MM = 20;
const KNIFE_VELOCITY_MAX_CM_S = 50;

function updateSceneFromFrame(refs: SceneRefs, frame: SimulationFrame) {
  const depthFactor = frame.knife_state.depth / CUT_DEPTH_MAX_MM;
  const velocityFactor = frame.knife_state.velocity / KNIFE_VELOCITY_MAX_CM_S;
  const locationY = 4.1 - frame.knife_state.location_from_top * 6.1;
  refs.knife.position.set(-2.55 + depthFactor * 1.25, locationY, 1.1);
  refs.knife.rotation.set(0.08, -0.14, THREE.MathUtils.degToRad(frame.knife_state.angle));
  refs.knife.scale.y = 0.86 + velocityFactor * 0.25;

  refs.cutGroup.clear();
  frame.cut_marks.forEach((mark) => {
    const y = 4.0 - mark.location_from_top * 6.0;
    const radius = 1.18 + (1 - mark.location_from_top) * 0.72;
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(0.04, 0.52, 0.018),
      new THREE.MeshBasicMaterial({ color: '#1f0e09', transparent: true, opacity: 0.78 })
    );
    mesh.position.set(Math.sin(mark.angle) * radius, y, Math.cos(mark.angle) * radius);
    mesh.lookAt(0, y, 0);
    refs.cutGroup.add(mesh);
  });

  if (frame.latest_slice) {
    refs.slice.visible = true;
    refs.slice.position.set(-1.55, locationY - 0.5, 1.7);
    refs.slice.rotation.set(0.18, frame.rotation_angle * 0.2, 0.5);
    refs.slice.scale.set(
      Math.max(0.65, frame.latest_slice.surface_area_cm2 / 42),
      1,
      Math.max(0.55, frame.latest_slice.thickness_mm / 4.8)
    );
  } else {
    refs.slice.visible = false;
  }
}
