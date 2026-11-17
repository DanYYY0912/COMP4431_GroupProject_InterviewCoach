import * as THREE from 'three';
import { FaceRig, blinkAt, speechOpening, validateFaceMesh } from './faceRig';

export type InterviewerMotion = {
  speaking: boolean;
  speechCue: number;
  state: string;
  reduced: boolean;
};

export async function createPortraitScene(
  host: HTMLElement,
  src: string,
  meshSrc: string,
  motion: () => InterviewerMotion,
  signal: AbortSignal,
  failed: () => void,
) {
  const response = await fetch(meshSrc, { signal });
  if (!response.ok) throw new Error('Could not load the interviewer mesh.');
  const rig = new FaceRig(validateFaceMesh(await response.json()));
  const image = new Image();
  image.src = src;
  await image.decode();
  signal.throwIfAborted();
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  const resources: Array<() => void> = [
    () => renderer.dispose(),
    () => renderer.domElement.remove(),
  ];
  let frame = 0;
  let disposed = false;
  function dispose() {
    if (disposed) return;
    disposed = true;
    cancelAnimationFrame(frame);
    signal.removeEventListener('abort', dispose);
    for (const release of resources.reverse()) release();
  }
  signal.addEventListener('abort', dispose, { once: true });
  try {
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.setClearColor('#d7d7d7');
    const scene = new THREE.Scene();
    const group = new THREE.Group();
    const camera = new THREE.OrthographicCamera(-1, 1, rig.ratio, -rig.ratio, 0.1, 20);
    camera.position.z = 5;
    const texture = new THREE.Texture(image);
    resources.push(() => texture.dispose());
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    const geometry = new THREE.BufferGeometry();
    resources.push(() => geometry.dispose());
    const positions = new THREE.BufferAttribute(rig.positions, 3).setUsage(THREE.DynamicDrawUsage);
    geometry.setAttribute('position', positions);
    geometry.setAttribute('uv', new THREE.BufferAttribute(rig.uv, 2));
    geometry.setIndex(rig.data.triangles);
    const material = new THREE.MeshBasicMaterial({ map: texture, side: THREE.DoubleSide });
    resources.push(() => material.dispose());
    const surface = new THREE.Mesh(geometry, material);
    surface.frustumCulled = false;
    group.add(surface);
    const interior = new THREE.BufferGeometry();
    resources.push(() => interior.dispose());
    const mouthPositions = new THREE.BufferAttribute(rig.mouth, 3).setUsage(THREE.DynamicDrawUsage);
    interior.setAttribute('position', mouthPositions);
    const mouthIndices = rig.data.mouthLoop.flatMap((_, i, loop) => [
      0,
      i + 1,
      ((i + 1) % loop.length) + 1,
    ]);
    interior.setIndex(mouthIndices);
    const mouthMaterial = new THREE.MeshBasicMaterial({ color: '#301719', side: THREE.DoubleSide });
    resources.push(() => mouthMaterial.dispose());
    const mouth = new THREE.Mesh(interior, mouthMaterial);
    mouth.frustumCulled = false;
    group.add(mouth);
    scene.add(group);
    // Slight overscan keeps the photographed backdrop inside the frame during restrained head motion.
    group.scale.setScalar(1.015);
    host.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-hidden', 'true');
    let resizeDirty = true;
    const resize = () => {
      if (!disposed && host.clientWidth && host.clientHeight) {
        renderer.setSize(host.clientWidth, host.clientHeight, false);
        resizeDirty = true;
      }
    };
    const observer = new ResizeObserver(resize);
    resources.push(() => observer.disconnect());
    observer.observe(host);
    resize();
    let lastRender = -100;
    let speakingStarted = performance.now();
    let wasSpeaking = false;
    let wasStill = false;
    const started = performance.now();
    function tick(now: number) {
      if (disposed) return;
      frame = requestAnimationFrame(tick);
      if (document.hidden || now - lastRender < 32) return;
      lastRender = now;
      const current = motion();
      const still = current.reduced || current.state === 'paused';
      if (still && wasStill && !resizeDirty) return;
      wasStill = still;
      resizeDirty = false;
      const seconds = (now - started) / 1000;
      if (current.speaking && !wasSpeaking) speakingStarted = now;
      wasSpeaking = current.speaking;
      const opening =
        current.speaking && !still
          ? speechOpening((now - speakingStarted) / 1000, current.speechCue)
          : 0;
      rig.pose(opening, still ? 0 : blinkAt(seconds + 1));
      positions.needsUpdate = true;
      mouthPositions.needsUpdate = true;
      group.rotation.y = still ? 0 : Math.sin(seconds * 0.43) * 0.012;
      group.rotation.x = still ? 0 : Math.sin(seconds * 0.71) * (current.speaking ? 0.007 : 0.003);
      group.rotation.z = still ? 0 : Math.sin(seconds * 0.34) * 0.002;
      try {
        renderer.render(scene, camera);
      } catch {
        dispose();
        failed();
      }
    }
    const lost = (event: Event) => {
      event.preventDefault();
      dispose();
      failed();
    };
    renderer.domElement.addEventListener('webglcontextlost', lost);
    resources.push(() => renderer.domElement.removeEventListener('webglcontextlost', lost));
    tick(performance.now());
    return dispose;
  } catch (error) {
    dispose();
    throw error;
  }
}
