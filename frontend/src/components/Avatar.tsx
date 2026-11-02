import { Component, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import type { Group, Mesh } from 'three';

function Portrait() {
  return (
    <svg
      className="avatar-portrait"
      viewBox="0 0 320 340"
      role="img"
      aria-label="Illustrated interview coach"
    >
      <circle cx="160" cy="148" r="126" fill="#d8e3d6" />
      <path d="M59 340v-55c0-56 45-76 101-76s101 20 101 76v55" fill="#183f38" />
      <path d="m125 221 35 65 35-65" fill="#f5eee0" />
      <rect x="142" y="184" width="36" height="54" rx="16" fill="#ba866a" />
      <ellipse cx="160" cy="139" rx="61" ry="77" fill="#cc9779" />
      <path
        d="M100 138c-13-64 19-95 61-95 45 0 72 32 59 94l-12-35c-31 7-53-3-69-17-8 23-24 35-39 39z"
        fill="#29352e"
      />
      <path d="M123 137h18m38 0h18" stroke="#28342f" strokeWidth="5" strokeLinecap="round" />
      <circle cx="133" cy="149" r="3" fill="#26332c" />
      <circle cx="188" cy="149" r="3" fill="#26332c" />
      <path
        d="m159 153-5 21h12m-23 17c9 7 25 7 34-1"
        fill="none"
        stroke="#8d5849"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="m123 225-13 48 32-10m55-38 13 48-32-10"
        fill="none"
        stroke="#477067"
        strokeWidth="2"
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

function Interviewer({
  mouth,
  state,
  reduced,
}: {
  mouth: number;
  state: string;
  reduced: boolean;
}) {
  const head = useRef<Group>(null);
  const lip = useRef<Mesh>(null);
  const eyes = useRef<Group>(null);
  useFrame(({ clock }) => {
    const time = clock.getElapsedTime();
    if (head.current) {
      head.current.rotation.z = reduced ? 0 : Math.sin(time * 0.65) * 0.016;
      head.current.rotation.y = reduced ? 0 : Math.sin(time * 0.35) * 0.035;
      head.current.position.y = 0.43 + (reduced ? 0 : Math.sin(time * 1.1) * 0.012);
    }
    if (lip.current) lip.current.scale.y = 0.28 + mouth * 2.4;
    if (eyes.current) eyes.current.scale.y = !reduced && time % 5.3 > 5.15 ? 0.12 : 1;
  });
  return (
    <group position={[0, -0.25, 0]}>
      <mesh position={[0, -0.75, 0]} scale={[0.9, 1, 0.46]}>
        <sphereGeometry args={[0.65, 32, 24]} />
        <meshStandardMaterial color="#24574c" roughness={0.9} />
      </mesh>
      <mesh position={[0, -0.36, 0.31]} rotation={[0, 0, Math.PI / 4]} scale={[0.25, 0.4, 0.04]}>
        <boxGeometry />
        <meshStandardMaterial color="#f5eee0" />
      </mesh>
      <mesh position={[0, -0.09, 0]}>
        <cylinderGeometry args={[0.13, 0.18, 0.35, 24]} />
        <meshStandardMaterial color="#b98568" />
      </mesh>
      <group ref={head} position={[0, 0.43, 0]}>
        <mesh scale={[0.42, 0.53, 0.38]}>
          <sphereGeometry args={[1, 48, 32]} />
          <meshStandardMaterial color="#cd9a7c" roughness={0.85} />
        </mesh>
        <mesh position={[0, 0.24, -0.035]} scale={[0.445, 0.36, 0.4]} rotation={[0, 0, 0.16]}>
          <sphereGeometry args={[1, 32, 24, 0, Math.PI * 2, 0, Math.PI * 0.7]} />
          <meshStandardMaterial color="#26382f" roughness={1} />
        </mesh>
        {[-1, 1].map((side) => (
          <mesh key={`ear-${side}`} position={[side * 0.405, -0.01, 0]} scale={[0.065, 0.12, 0.07]}>
            <sphereGeometry args={[1, 16, 12]} />
            <meshStandardMaterial color="#c18a70" />
          </mesh>
        ))}
        <group ref={eyes}>
          {[-1, 1].map((side) => (
            <group key={`eye-${side}`} position={[side * 0.15, 0.035, 0.344]}>
              <mesh scale={[0.055, 0.027, 0.023]}>
                <sphereGeometry args={[1, 24, 12]} />
                <meshStandardMaterial color="#f8eee1" />
              </mesh>
              <mesh position={[0, 0, 0.02]}>
                <sphereGeometry args={[0.022, 16, 12]} />
                <meshStandardMaterial color="#24362c" />
              </mesh>
              <mesh position={[0.006, 0.007, 0.036]}>
                <sphereGeometry args={[0.006, 10, 8]} />
                <meshBasicMaterial color="#fff" />
              </mesh>
            </group>
          ))}
        </group>
        {[-1, 1].map((side) => (
          <mesh
            key={`brow-${side}`}
            position={[side * 0.15, 0.12, 0.342]}
            rotation={[0, 0, side * (state === 'thinking' ? 0.15 : -0.05)]}
            scale={[0.065, 0.011, 0.012]}
          >
            <sphereGeometry args={[1, 16, 8]} />
            <meshStandardMaterial color="#3d3c2e" />
          </mesh>
        ))}
        <mesh position={[0, -0.075, 0.382]} scale={[0.043, 0.073, 0.064]}>
          <sphereGeometry args={[1, 20, 16]} />
          <meshStandardMaterial color="#bb866b" />
        </mesh>
        <mesh ref={lip} position={[0, -0.225, 0.332]} scale={[1, 0.3, 1]}>
          <sphereGeometry args={[0.066, 24, 16]} />
          <meshStandardMaterial color="#713e35" roughness={0.9} />
        </mesh>
      </group>
    </group>
  );
}

export default function Avatar({
  mouth,
  state,
  disabled,
}: {
  mouth: number;
  state: string;
  disabled: boolean;
}) {
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
          camera={{ position: [0, 0.25, 3.3], fov: 38 }}
          dpr={[1, 1.5]}
          fallback={<Portrait />}
          gl={{ antialias: true, alpha: true }}
        >
          <ambientLight intensity={2} />
          <directionalLight position={[-3, 4, 5]} intensity={2.4} color="#fff6de" />
          <directionalLight position={[3, 1, -3]} intensity={1.2} color="#b8d7c2" />
          <Interviewer mouth={mouth} state={state} reduced={reduced} />
        </Canvas>
      </CanvasBoundary>
    </div>
  );
}
