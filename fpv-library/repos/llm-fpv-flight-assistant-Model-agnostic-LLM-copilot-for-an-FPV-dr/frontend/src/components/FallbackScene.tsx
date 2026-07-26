import { Canvas } from "@react-three/fiber";
import { Grid } from "@react-three/drei";
import type { Telemetry } from "../types";

const D = Math.PI / 180;

export function FallbackScene({ t }: { t: Telemetry | null }) {
  const alt = t ? Math.max(0.2, t.alt_m / 10) : 0.2;
  const rot: [number, number, number] = t
    ? [(t.pitch ?? 0) * D, (t.yaw ?? 0) * D, (t.roll ?? 0) * D]
    : [0, 0, 0];
  return (
    <Canvas camera={{ position: [4, 3, 5], fov: 55 }} style={{ width: "100%", height: "100%" }}>
      <ambientLight intensity={0.6} />
      <directionalLight position={[5, 8, 5]} intensity={0.8} />
      <Grid args={[40, 40]} cellColor="#1f6feb" sectionColor="#30363d" infiniteGrid />
      <mesh position={[0, alt, 0]} rotation={rot}>
        <boxGeometry args={[0.8, 0.2, 0.8]} />
        <meshStandardMaterial color="#3fb950" />
      </mesh>
    </Canvas>
  );
}
