import { Component, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { DoubleSide, MathUtils, Shape, Vector2 } from 'three';
import type { Group, Mesh } from 'three';

const COLORS = {
  skin: '#e2ae8c',
  skinShade: '#d39c7b',
  hair: '#2b221d',
  jacket: '#1f4d43',
  lapel: '#173b33',
  shirt: '#f7f3ea',
  tie: '#a9c25e',
  lips: '#b86a5c',
  mouth: '#5b2a26',
  iris: '#4a3326',
  blush: '#ef9c86',
} as const;

// Damping rates (per second) for the eased transitions between coach states.
const EASE_FAST = 14;
const EASE_SLOW = 5;
const BLINK_SECONDS = 0.13;

interface AvatarProps {
  mouth: number;
  state: string;
  disabled: boolean;
}

interface InterviewerProps {
  mouth: number;
  state: string;
}

type Profile = ReadonlyArray<readonly [number, number]>;

function Portrait() {
  return (
    <svg
      className="avatar-portrait"
      viewBox="0 0 320 340"
      role="img"
      aria-label="Illustrated interview coach"
    >
      <circle cx="160" cy="148" r="126" fill="#d8e3d6" />
      <path d="M59 340v-55c0-56 45-76 101-76s101 20 101 76v55" fill={COLORS.jacket} />
      <path d="m125 221 35 65 35-65" fill={COLORS.shirt} />
      <path d="m153 226 7-8 7 8-7 52z" fill={COLORS.tie} />
      <rect x="142" y="184" width="36" height="40" rx="16" fill={COLORS.skinShade} />
      <ellipse cx="160" cy="139" rx="61" ry="77" fill={COLORS.skin} />
      <path
        d="M100 138c-13-64 19-95 61-95 45 0 72 32 59 94l-12-35c-31 7-53-3-69-17-8 23-24 35-39 39z"
        fill={COLORS.hair}
      />
      <path d="M123 133h18m38 0h18" stroke={COLORS.hair} strokeWidth="5" strokeLinecap="round" />
      <circle cx="133" cy="149" r="4" fill={COLORS.iris} />
      <circle cx="188" cy="149" r="4" fill={COLORS.iris} />
      <path
        d="M140 186c10 9 30 9 40 0"
        fill="none"
        stroke={COLORS.lips}
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

class CanvasBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <Portrait /> : this.props.children;
  }
}

function lathePoints(profile: Profile) {
  return profile.map(([radius, height]) => new Vector2(radius, height));
}

function polygon(points: Profile) {
  const shape = new Shape();
  points.forEach(([x, y], index) => (index ? shape.lineTo(x, y) : shape.moveTo(x, y)));
  shape.closePath();
  return shape;
}

const HEAD_PROFILE: Profile = [
  [0, -0.5],
  [0.15, -0.485],
  [0.27, -0.41],
  [0.355, -0.27],
  [0.395, -0.09],
  [0.405, 0.08],
  [0.385, 0.24],
  [0.33, 0.38],
  [0.22, 0.475],
  [0, 0.52],
];

const TORSO_PROFILE: Profile = [
  [0.56, -0.8],
  [0.63, -0.45],
  [0.66, -0.22],
  [0.6, -0.04],
  [0.42, 0.07],
  [0.2, 0.12],
  [0.14, 0.13],
];

const CHEST_SHAPES: Record<string, Profile> = {
  shirt: [
    [-0.16, 0],
    [0.16, 0],
    [0, -0.34],
  ],
  lapelLeft: [
    [-0.17, 0.01],
    [-0.27, -0.03],
    [-0.05, -0.36],
    [-0.01, -0.33],
  ],
  lapelRight: [
    [0.17, 0.01],
    [0.27, -0.03],
    [0.05, -0.36],
    [0.01, -0.33],
  ],
  tie: [
    [-0.026, -0.03],
    [0.026, -0.03],
    [0.042, -0.24],
    [0, -0.3],
    [-0.042, -0.24],
  ],
  knot: [
    [-0.04, 0.012],
    [0.04, 0.012],
    [0.026, -0.04],
    [-0.026, -0.04],
  ],
};

const CHEST_LAYERS = [
  { shape: 'shirt', color: COLORS.shirt, z: 0 },
  { shape: 'lapelLeft', color: COLORS.lapel, z: 0.004 },
  { shape: 'lapelRight', color: COLORS.lapel, z: 0.004 },
  { shape: 'tie', color: COLORS.tie, z: 0.003 },
  { shape: 'knot', color: COLORS.tie, z: 0.005 },
] as const;

function Torso({ breath }: { breath: RefObject<Group | null> }) {
  const torso = useMemo(() => lathePoints(TORSO_PROFILE), []);
  const shapes = useMemo(
    () => Object.fromEntries(Object.entries(CHEST_SHAPES).map(([key, pts]) => [key, polygon(pts)])),
    [],
  );
  return (
    <group ref={breath} position={[0, -0.47, 0]}>
      <mesh scale={[0.92, 1, 0.5]}>
        <latheGeometry args={[torso, 48]} />
        <meshStandardMaterial color={COLORS.jacket} roughness={0.85} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.15, 0.165, 0.32, 28]} />
        <meshStandardMaterial color={COLORS.skinShade} roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.07, 0]}>
        <cylinderGeometry args={[0.178, 0.19, 0.09, 28, 1, true]} />
        <meshStandardMaterial color={COLORS.shirt} roughness={0.7} side={DoubleSide} />
      </mesh>
      <group position={[0, 0.06, 0.24]} rotation={[-0.42, 0, 0]}>
        {CHEST_LAYERS.map((layer) => (
          <mesh key={layer.shape} position={[0, 0, layer.z]}>
            <shapeGeometry args={[shapes[layer.shape]]} />
            <meshStandardMaterial color={layer.color} roughness={0.7} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// Hair follows the head profile 0.022 further out so it never exposes the scalp.
const HAIR_TOP_PROFILE: Profile = [
  [0.392, 0.17],
  [0.428, 0.18],
  [0.41, 0.25],
  [0.356, 0.385],
  [0.242, 0.49],
  [0, 0.546],
];

const HAIR_BACK_PROFILE: Profile = [
  [0.33, -0.2],
  [0.385, -0.16],
  [0.418, -0.06],
  [0.428, 0.08],
  [0.428, 0.2],
];

function Hair() {
  const top = useMemo(() => lathePoints(HAIR_TOP_PROFILE), []);
  const back = useMemo(() => lathePoints(HAIR_BACK_PROFILE), []);
  return (
    <group scale={[1, 1, 0.9]}>
      <mesh>
        <latheGeometry args={[top, 48]} />
        <meshStandardMaterial color={COLORS.hair} roughness={0.95} side={DoubleSide} />
      </mesh>
      <mesh>
        <latheGeometry args={[back, 40, Math.PI * 0.42, Math.PI * 1.16]} />
        <meshStandardMaterial color={COLORS.hair} roughness={0.95} side={DoubleSide} />
      </mesh>
      <mesh position={[0.07, 0.31, 0.33]} rotation={[-0.45, 0.1, -0.22]} scale={[0.25, 0.07, 0.1]}>
        <sphereGeometry args={[1, 28, 16]} />
        <meshStandardMaterial color={COLORS.hair} roughness={0.95} />
      </mesh>
    </group>
  );
}

function Eye({ side, gaze }: { side: number; gaze: RefObject<Group | null> }) {
  return (
    <group position={[side * 0.142, 0.045, 0.332]}>
      <mesh scale={[0.064, 0.047, 0.032]}>
        <sphereGeometry args={[1, 24, 16]} />
        <meshStandardMaterial color="#fbf6ef" roughness={0.4} />
      </mesh>
      <group ref={gaze}>
        <mesh position={[0, 0, 0.026]} scale={[1, 1, 0.45]}>
          <sphereGeometry args={[0.03, 20, 14]} />
          <meshStandardMaterial color={COLORS.iris} roughness={0.35} />
        </mesh>
        <mesh position={[0, 0, 0.034]}>
          <sphereGeometry args={[0.013, 14, 10]} />
          <meshStandardMaterial color="#14100d" roughness={0.2} />
        </mesh>
        <mesh position={[0.009, 0.01, 0.042]}>
          <sphereGeometry args={[0.0065, 10, 8]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      </group>
    </group>
  );
}

interface FaceRefs {
  eyes: RefObject<Group | null>;
  gaze: readonly [RefObject<Group | null>, RefObject<Group | null>];
  brows: RefObject<Group | null>;
  mouthOpen: RefObject<Mesh | null>;
}

function Face({ eyes, gaze, brows, mouthOpen }: FaceRefs) {
  return (
    <group>
      <group ref={eyes}>
        <Eye side={-1} gaze={gaze[0]} />
        <Eye side={1} gaze={gaze[1]} />
      </group>
      <group ref={brows}>
        {[-1, 1].map((side) => (
          <mesh
            key={side}
            position={[side * 0.145, 0.145, 0.352]}
            rotation={[0, side * 0.25, Math.PI / 2 + side * 0.08]}
          >
            <capsuleGeometry args={[0.0135, 0.07, 4, 10]} />
            <meshStandardMaterial color={COLORS.hair} roughness={0.9} />
          </mesh>
        ))}
      </group>
      <mesh position={[0, -0.035, 0.37]} scale={[0.036, 0.05, 0.04]}>
        <sphereGeometry args={[1, 20, 14]} />
        <meshStandardMaterial color={COLORS.skinShade} roughness={0.75} />
      </mesh>
      {[-1, 1].map((side) => (
        <mesh key={side} position={[side * 0.2, -0.075, 0.322]} rotation={[0, side * 0.55, 0]}>
          <circleGeometry args={[0.05, 24]} />
          <meshStandardMaterial
            color={COLORS.blush}
            transparent
            opacity={0.28}
            depthWrite={false}
          />
        </mesh>
      ))}
      <mesh position={[0, -0.112, 0.348]} rotation={[0, 0, -Math.PI / 2 - Math.PI * 0.3]}>
        <torusGeometry args={[0.058, 0.0085, 8, 28, Math.PI * 0.6]} />
        <meshStandardMaterial color={COLORS.lips} roughness={0.6} />
      </mesh>
      <mesh ref={mouthOpen} position={[0, -0.168, 0.338]} scale={[0.045, 0.004, 0.02]}>
        <sphereGeometry args={[1, 20, 12]} />
        <meshStandardMaterial color={COLORS.mouth} roughness={0.9} />
      </mesh>
    </group>
  );
}

function Interviewer({ mouth, state }: InterviewerProps) {
  const head = useRef<Group>(null);
  const breath = useRef<Group>(null);
  const eyes = useRef<Group>(null);
  const gazeLeft = useRef<Group>(null);
  const gazeRight = useRef<Group>(null);
  const brows = useRef<Group>(null);
  const mouthOpen = useRef<Mesh>(null);
  const motion = useRef({ mouth: 0, nextBlink: 2, blinkUntil: 0 });
  const headProfile = useMemo(() => lathePoints(HEAD_PROFILE), []);

  useFrame(({ clock }, delta) => {
    const time = clock.getElapsedTime();
    const live = motion.current;
    const thinking = state === 'thinking' || state === 'transcribing';
    const listening = state === 'listening';
    const speaking = state === 'speaking';
    const damp = (from: number, to: number, rate = EASE_SLOW) =>
      MathUtils.damp(from, to, rate, delta);

    live.mouth = damp(live.mouth, speaking ? mouth : 0, EASE_FAST);
    if (time > live.nextBlink) {
      live.blinkUntil = time + BLINK_SECONDS;
      live.nextBlink = time + 2.4 + Math.random() * 3.6;
    }
    if (head.current) {
      const nod = listening ? Math.sin(time * 1.4) * 0.035 : 0;
      const tilt = thinking ? 0.09 : listening ? -0.05 : Math.sin(time * 0.6) * 0.02;
      const turn = thinking ? -0.12 : Math.sin(time * 0.33) * 0.05;
      const pitch = (thinking ? -0.06 : 0) + nod + live.mouth * 0.25;
      head.current.rotation.z = damp(head.current.rotation.z, tilt);
      head.current.rotation.y = damp(head.current.rotation.y, turn);
      head.current.rotation.x = damp(head.current.rotation.x, pitch);
    }
    if (breath.current) breath.current.scale.y = 1 + Math.sin(time * 1.5) * 0.008;
    if (eyes.current) eyes.current.scale.y = time < live.blinkUntil ? 0.1 : 1;
    const glance = Math.sin(time * 0.45) > 0.92 ? 0.012 : 0;
    for (const pupils of [gazeLeft.current, gazeRight.current]) {
      if (!pupils) continue;
      pupils.position.x = damp(pupils.position.x, thinking ? -0.014 : glance);
      pupils.position.y = damp(pupils.position.y, thinking ? 0.012 : 0);
    }
    if (brows.current) {
      const raise = thinking ? 0.016 : listening ? 0.008 : live.mouth * 0.05;
      brows.current.position.y = damp(brows.current.position.y, raise);
    }
    if (mouthOpen.current) mouthOpen.current.scale.y = 0.004 + Math.min(live.mouth, 0.3) * 0.16;
  });

  return (
    <group position={[0, -0.12, 0]}>
      <Torso breath={breath} />
      <group ref={head} position={[0, 0.3, 0]}>
        <mesh scale={[1, 1, 0.9]}>
          <latheGeometry args={[headProfile, 48]} />
          <meshStandardMaterial color={COLORS.skin} roughness={0.75} />
        </mesh>
        {[-1, 1].map((side) => (
          <mesh key={side} position={[side * 0.395, 0, -0.02]} scale={[0.05, 0.1, 0.065]}>
            <sphereGeometry args={[1, 16, 12]} />
            <meshStandardMaterial color={COLORS.skinShade} roughness={0.8} />
          </mesh>
        ))}
        <Hair />
        <Face eyes={eyes} gaze={[gazeLeft, gazeRight]} brows={brows} mouthOpen={mouthOpen} />
      </group>
    </group>
  );
}

export default function Avatar({ mouth, state, disabled }: AvatarProps) {
  const [reduced, setReduced] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  );
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(media.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  if (disabled || reduced) return <Portrait />;
  return (
    <div className="avatar-canvas" role="img" aria-label={`3D interview coach, ${state}`}>
      <CanvasBoundary>
        <Canvas
          camera={{ position: [0, 0, 3.1], fov: 33 }}
          dpr={[1, 2]}
          fallback={<Portrait />}
          gl={{ antialias: true, alpha: true }}
        >
          <hemisphereLight args={['#fff6e6', '#41604f', 1.4]} />
          <ambientLight intensity={0.6} />
          <directionalLight position={[-2.5, 3, 4]} intensity={2.4} color="#fff1dc" />
          <directionalLight position={[2.8, 1.6, -3]} intensity={2.2} color="#cfe9d4" />
          <Interviewer mouth={mouth} state={state} />
        </Canvas>
      </CanvasBoundary>
    </div>
  );
}
