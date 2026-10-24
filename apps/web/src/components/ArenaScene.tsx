"use client";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, Line, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import type { Group, Mesh } from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import type { CommitmentState, PlanStatus } from "@/lib/events/types";
import { buildSceneModel, ringPosition, SceneModel } from "@/lib/scene/model";
import type { MissionView } from "@/lib/events/types";

const R = 3.4;

const STATE_COLOR: Record<CommitmentState | "unknown" | "pending", string> = {
  accepted: "#4ade80",
  pending: "#fbbf24",
  conditional: "#c4b5fd",
  interested: "#7dd3fc",
  tentative: "#7dd3fc",
  declined: "#fb7185",
  withdrawn: "#fb7185",
  unknown: "#64748b",
};
const STATUS_COLOR: Record<PlanStatus | "none", string> = {
  none: "#475569",
  proposed: "#22d3ee",
  rejected: "#fb7185",
  ready: "#fbbf24",
  awaiting_approval: "#fbbf24",
  confirmed: "#4ade80",
  superseded: "#64748b",
  failed: "#94a3b8",
};

function useAnim(reduced: boolean, fn: (t: number, dt: number) => void) {
  useFrame((s, dt) => {
    if (!reduced) fn(s.clock.elapsedTime, dt);
  });
}

function AgentNode({ state, position, label, sub, reduced }: { state: CommitmentState | "unknown"; position: [number, number, number]; label: string; sub: string; reduced: boolean }) {
  const ref = useRef<Group>(null);
  const color = STATE_COLOR[state];
  useAnim(reduced, (t) => {
    if (!ref.current) return;
    if (state === "pending" || state === "unknown") ref.current.scale.setScalar(1 + Math.sin(t * 2) * 0.05);
    else ref.current.scale.setScalar(1);
  });
  const solid = state === "accepted";
  return (
    <group position={position}>
      <group ref={ref}>
        {state === "declined" || state === "withdrawn" ? (
          <mesh><octahedronGeometry args={[0.42]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.25} flatShading /></mesh>
        ) : state === "conditional" ? (
          <>
            <mesh><sphereGeometry args={[0.38, 24, 24]} /><meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.3} transparent opacity={0.55} /></mesh>
            <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.6, 0.035, 8, 40, Math.PI * 1.4]} /><meshBasicMaterial color={color} /></mesh>
          </>
        ) : (
          <mesh>
            <icosahedronGeometry args={[0.42, solid ? 3 : 1]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={solid ? 0.55 : 0.15} wireframe={!solid} transparent opacity={solid ? 1 : 0.9} />
          </mesh>
        )}
        {solid && (
          <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.62, 0.025, 8, 48]} /><meshBasicMaterial color={color} /></mesh>
        )}
      </group>
      <Html center position={[0, -0.95, 0]} style={{ pointerEvents: "none" }} zIndexRange={[5, 0]}>
        <div style={{ textAlign: "center", whiteSpace: "nowrap", fontSize: 12, color: "#e8edfb", textShadow: "0 1px 6px #000" }}>
          <b>{label}</b>
          <div style={{ color, fontSize: 11 }}>{sub}</div>
        </div>
      </Html>
    </group>
  );
}

function Shards({ color, reduced, scale = 1 }: { color: string; reduced: boolean; scale?: number }) {
  const g = useRef<Group>(null);
  const dirs = useMemo(() => Array.from({ length: 9 }, (_, i) => {
    const a = (i / 9) * Math.PI * 2;
    return [Math.cos(a), ((i % 3) - 1) * 0.5, Math.sin(a)] as [number, number, number];
  }), []);
  useAnim(reduced, (t) => {
    if (g.current) g.current.rotation.y = t * 0.15;
  });
  return (
    <group ref={g} scale={scale}>
      {dirs.map((d, i) => (
        <mesh key={i} position={[d[0] * 0.42, d[1] * 0.4, d[2] * 0.42]} rotation={[i, i * 0.7, i * 1.3]}>
          <tetrahedronGeometry args={[0.2]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.4} flatShading />
        </mesh>
      ))}
    </group>
  );
}

function PlanCore({ model, reduced }: { model: SceneModel; reduced: boolean }) {
  const m = useRef<Mesh>(null);
  const status = model.core.status;
  const color = STATUS_COLOR[status];
  useAnim(reduced, (t, dt) => {
    if (!m.current) return;
    m.current.rotation.y += dt * (status === "proposed" ? 0.8 : 0.25);
    if (status === "awaiting_approval" || status === "ready") m.current.scale.setScalar(1 + Math.sin(t * 1.6) * 0.04);
  });
  const p = model.core.progress;
  return (
    <group>
      {status === "rejected" ? (
        <Shards color={color} reduced={reduced} />
      ) : status === "none" ? (
        <mesh><sphereGeometry args={[0.12, 12, 12]} /><meshBasicMaterial color={color} /></mesh>
      ) : status === "failed" ? (
        <mesh><octahedronGeometry args={[0.55]} /><meshStandardMaterial color="#334155" emissive="#fb7185" emissiveIntensity={0.15} flatShading /></mesh>
      ) : (
        <mesh ref={m}>
          {status === "confirmed" ? <dodecahedronGeometry args={[0.62]} /> : <icosahedronGeometry args={[0.62, status === "proposed" ? 1 : 0]} />}
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={status === "confirmed" ? 0.7 : 0.3} wireframe={status === "proposed"} transparent opacity={status === "awaiting_approval" || status === "ready" ? 0.65 : 1} flatShading />
        </mesh>
      )}
      {/* Approval progress arc: filled portion = accepted / required, from backend counts. */}
      {p !== null && (
        <>
          <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.05, 0.03, 8, 64]} /><meshBasicMaterial color="#334155" /></mesh>
          {p > 0 && <mesh rotation={[Math.PI / 2, 0, Math.PI / 2]}><torusGeometry args={[1.05, 0.06, 8, 64, Math.min(1, p) * Math.PI * 2]} /><meshBasicMaterial color="#4ade80" /></mesh>}
        </>
      )}
      {status === "confirmed" && <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.35, 0.04, 8, 64]} /><meshBasicMaterial color="#4ade80" /></mesh>}
      {model.conflict?.active && status !== "failed" && (
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[1.25, 0.05, 6, 9]} /><meshBasicMaterial color="#fb7185" wireframe /></mesh>
      )}
      <Html center position={[0, 1.35, 0]} style={{ pointerEvents: "none" }}>
        <div style={{ whiteSpace: "nowrap", fontSize: 12, color: "#e8edfb", textShadow: "0 1px 6px #000", textAlign: "center" }}>
          <b style={{ color }}>{model.core.text}</b>
        </div>
      </Html>
    </group>
  );
}

function VersionSpine({ model, reduced }: { model: SceneModel; reduced: boolean }) {
  return (
    <group position={[-R - 3.3, 0, 0]}>
      {model.versions.map((v, i) => {
        const y = (model.versions.length - 1) / 2 * 0.9 - i * 0.9;
        const c = STATUS_COLOR[v.status];
        return (
          <group key={v.version} position={[0, y, 0]}>
            {v.status === "rejected" ? <Shards color={c} reduced={reduced} scale={0.55} /> : (
              <mesh><sphereGeometry args={[v.current ? 0.26 : 0.18, 16, 16]} /><meshStandardMaterial color={c} emissive={c} emissiveIntensity={v.current ? 0.6 : 0.15} /></mesh>
            )}
            <Html position={[0.55, 0, 0]} style={{ pointerEvents: "none" }}>
              <div style={{ whiteSpace: "nowrap", fontSize: 11, color: c, textShadow: "0 1px 6px #000" }}>v{v.version} {v.status.replace("_", " ")}</div>
            </Html>
          </group>
        );
      })}
    </group>
  );
}

function World({ view, reduced }: { view: MissionView; reduced: boolean }) {
  const model = useMemo(() => buildSceneModel(view), [view]);
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => invalidate(), [model, invalidate]);
  const n = model.nodes.length;
  return (
    <>
      <ambientLight intensity={0.55} />
      <pointLight position={[0, 5, 4]} intensity={60} />
      <pointLight position={[-6, -2, -4]} intensity={25} color="#6366f1" />
      <gridHelper args={[16, 16, "#1e2a52", "#131b38"]} position={[0, -2.1, 0]} />
      <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[R, 0.012, 6, 96]} /><meshBasicMaterial color="#26325a" /></mesh>
      <PlanCore model={model} reduced={reduced} />
      {model.nodes.map((nd) => {
        const [x, z] = ringPosition(nd.slot, n);
        return <AgentNode key={nd.slot} state={nd.state} position={[x * R, 0, z * R]} label={nd.label} sub={`${nd.glyph} ${nd.state === "unknown" ? "unidentified" : nd.state}`} reduced={reduced} />;
      })}
      {model.edges.map((e) => {
        const [x, z] = ringPosition(e.slot, n);
        const c = STATE_COLOR[e.state];
        return <Line key={e.slot} points={[[0, 0, 0], [x * R, 0, z * R]]} color={c} lineWidth={e.kind === "responded" ? 2.4 : 1.2} dashed={e.kind === "requested" || e.state === "conditional"} dashSize={0.2} gapSize={0.15} transparent opacity={e.kind === "responded" ? 0.95 : 0.55} />;
      })}
      <VersionSpine model={model} reduced={reduced} />
    </>
  );
}

export interface ArenaSceneHandle {
  rotate(deg: number): void;
  reset(): void;
}

function Controls({ reduced, handleRef }: { reduced: boolean; handleRef: React.MutableRefObject<ArenaSceneHandle | null> }) {
  const c = useRef<OrbitControlsImpl>(null);
  const { camera, invalidate } = useThree();
  useEffect(() => {
    handleRef.current = {
      rotate: (deg) => {
        const ctl = c.current;
        if (!ctl) return;
        const az = ctl.getAzimuthalAngle() + (deg * Math.PI) / 180;
        const dist = camera.position.length();
        const polar = ctl.getPolarAngle();
        camera.position.set(dist * Math.sin(polar) * Math.sin(az), dist * Math.cos(polar), dist * Math.sin(polar) * Math.cos(az));
        ctl.update();
        invalidate();
      },
      reset: () => {
        camera.position.set(0, 9, 9.8);
        c.current?.update();
        invalidate();
      },
    };
  }, [camera, invalidate, handleRef]);
  return <OrbitControls ref={c} enablePan={false} enableDamping={!reduced} minDistance={5} maxDistance={16} maxPolarAngle={Math.PI * 0.62} makeDefault />;
}

export default function ArenaScene({ view, reduced, handleRef }: { view: MissionView; reduced: boolean; handleRef: React.MutableRefObject<ArenaSceneHandle | null> }) {
  return (
    <Canvas frameloop={reduced ? "demand" : "always"} dpr={[1, 1.75]} camera={{ position: [0, 9, 9.8], fov: 46 }} gl={{ antialias: true, alpha: true }} aria-label="3D negotiation arena" role="img">
      <World view={view} reduced={reduced} />
      <Controls reduced={reduced} handleRef={handleRef} />
    </Canvas>
  );
}
