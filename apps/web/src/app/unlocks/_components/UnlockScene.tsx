"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment } from "@react-three/drei/core/Environment";
import { Lightformer } from "@react-three/drei/core/Lightformer";
import { Float } from "@react-three/drei/core/Float";
import { RoundedBox } from "@react-three/drei/core/RoundedBox";
import { PerformanceMonitor } from "@react-three/drei/core/PerformanceMonitor";
import { Group, MathUtils, MeshBasicMaterial, MeshPhysicalMaterial } from "three";
import { makeCardTexture, makeGlowTexture } from "../_lib/cardTextures";
import type { UnlockSceneProps } from "../_lib/sceneTypes";
import { motion as config } from "../_lib/motion.config";

const labels = ["Student discount", "Campus gym", "Free software", "Arts workshop", "Local culture", "Weekend travel"];
const scattered = [[0, 0, .6], [-1.6, 1.65, -.7], [1.55, 1.25, -1.1], [-1.65, -1.45, -1], [1.7, -1.4, -.5], [.3, 2.65, -2]];
const mobileScattered = [[0, -.25, .6], [-.52, .85, -.5], [.5, 1, -.3]];
const mobileTilts = [-.035, .13, -.1];

function Card({ index, texture, glowTexture, ...props }: UnlockSceneProps & {
  index: number;
  texture: ReturnType<typeof makeCardTexture>;
  glowTexture: ReturnType<typeof makeGlowTexture>;
}) {
  const group = useRef<Group>(null);
  const material = useRef<MeshPhysicalMaterial>(null);
  const face = useRef<MeshBasicMaterial>(null);
  const viewport = useThree((state) => state.viewport);
  const anchor = props.motion.current.anchor;
  const origin = (props.mobile ? mobileScattered : scattered)[index]!;
  const initialSpread = props.mobile ? Math.min(1, viewport.width / 3) : 1;
  const [initialPosition] = useState<[number, number, number]>(() => [
    (anchor.x - .5) * viewport.width + origin[0]! * initialSpread,
    (.5 - anchor.y) * viewport.height + origin[1]! * initialSpread, origin[2]!,
  ]);
  useFrame((state, delta) => {
    const dt = Math.min(delta, .05);
    const progress = props.mobile ? 0 : props.motion.current.hero;
    const anchor = props.motion.current.anchor;
    const origin = (props.mobile ? mobileScattered : scattered)[index]!;
    const x = (anchor.x - .5) * state.viewport.width;
    const y = (.5 - anchor.y) * state.viewport.height;
    const spread = props.mobile ? Math.min(1, state.viewport.width / 3) : 1 - progress * .82;
    const pointer = props.motion.current.pointer;
    const response = config.scene.pointerResponse;
    const travel = props.mobile ? 0 : config.scene.pointerTravel * (1 - progress * .65);
    const current = group.current!;
    current.position.x = MathUtils.damp(current.position.x, x + origin[0]! * spread + pointer.x * travel, response, dt);
    current.position.y = MathUtils.damp(current.position.y, y + origin[1]! * spread - pointer.y * travel * .6, response, dt);
    current.position.z = MathUtils.damp(current.position.z, origin[2]! - (index ? progress * 2 : -progress * .3), 5, dt);
    const auto = props.mobile ? Math.sin(state.clock.elapsedTime * config.scene.mobileSpeed + index * .8) * .09 : 0;
    current.rotation.x = MathUtils.damp(current.rotation.x, props.mobile ? .03 : -pointer.y * config.scene.pointerTiltX * (1 - progress * .65), response, dt);
    current.rotation.y = MathUtils.damp(current.rotation.y, auto + (props.mobile ? 0 : (index - 2) * .12 * (1 - progress) + pointer.x * config.scene.pointerTiltY * (1 - progress * .65)), response, dt);
    current.rotation.z = MathUtils.damp(current.rotation.z, props.mobile ? mobileTilts[index]! : ((index % 2 ? -.12 : .1) * (1 - progress)), 5, dt);
    const opacity = index ? 1 - progress * .97 : 1;
    material.current!.opacity = face.current!.opacity = opacity;
    const scale = props.mobile
      ? index === 0 ? config.scene.mobilePrimaryScale : config.scene.mobileSecondaryScale
      : index === 0 ? 1 + progress * .1 : .78;
    current.scale.setScalar(scale);
  });
  return <group ref={group} position={initialPosition}>
    <Float speed={props.mobile ? config.scene.mobileFloatSpeed : config.scene.floatSpeed + index * config.scene.floatStep} rotationIntensity={props.mobile ? 0 : .16} floatIntensity={props.mobile ? .08 : .18}>
      <RoundedBox args={[2.75, 1.75, .16]} radius={.06} smoothness={3} bevelSegments={2}>
        <meshPhysicalMaterial ref={material} color={props.palette.paper} clearcoat={.3} clearcoatRoughness={.35} roughness={.48} metalness={.04} transparent />
      </RoundedBox>
      <mesh position={[0, 0, .087]}>
        <planeGeometry args={[2.59, 1.59]} />
        <meshBasicMaterial ref={face} map={texture} transparent toneMapped={false} />
      </mesh>
      {index === 0 && <mesh position={[0, -1.12, -.14]} scale={[4, .7, 1]}>
        <planeGeometry />
        <meshBasicMaterial map={glowTexture} transparent opacity={.24} depthWrite={false} toneMapped={false} />
      </mesh>}
    </Float>
  </group>;
}

function SceneContents(props: UnlockSceneProps) {
  const textures = useMemo(() => (props.mobile ? labels.slice(0, config.scene.mobileCards) : labels)
    .map((label, index) => makeCardTexture(label, index, props.palette)), [props.palette, props.mobile]);
  const glow = useMemo(() => makeGlowTexture(props.palette), [props.palette]);
  const didRender = useRef(false);
  const report = useRef({ time: 0, frames: 0 });
  useEffect(() => () => { textures.forEach((texture) => texture.dispose()); glow.dispose(); }, [textures, glow]);
  useFrame((state, delta) => {
    report.current.frames++;
    report.current.time += delta;
    if (state.gl.info.render.calls > 0 && report.current.frames > 2 && !didRender.current) {
      props.root.dataset.sceneDrawCalls = String(state.gl.info.render.calls);
      didRender.current = true;
      props.onReady();
    }
    if (report.current.time > .5) {
      props.root.dataset.sceneDrawCalls = String(state.gl.info.render.calls);
      props.root.dataset.sceneFrames = String(report.current.frames);
      props.root.dataset.sceneDpr = String(state.gl.getPixelRatio());
      report.current.time = 0;
    }
  });
  return <>
    <ambientLight intensity={.7} />
    <directionalLight position={[2, 5, 5]} intensity={1.8} color={props.palette.surface} />
    <Environment resolution={64} frames={1}>
      <Lightformer intensity={2} position={[0, 4, 5]} scale={[8, 3, 1]} color={props.palette.surface} />
      <Lightformer intensity={1} position={[-4, 0, 3]} scale={[3, 5, 1]} color={props.palette.paper} />
    </Environment>
    {textures.map((texture, index) => <Card {...props} key={index} index={index} texture={texture} glowTexture={glow} />)}
  </>;
}

export default function UnlockScene(props: UnlockSceneProps) {
  const [maxDpr, setMaxDpr] = useState(1.5);
  const cleanup = useRef<() => void>(() => {});
  useEffect(() => () => cleanup.current(), []);
  return <Canvas dpr={[1, maxDpr]} frameloop={props.active ? "always" : "never"}
    camera={{ position: [0, 0, 9], fov: 40 }} gl={{ alpha: true, antialias: true, powerPreference: "low-power" }}
    aria-hidden="true" style={{ pointerEvents: "none" }}
    onCreated={({ gl }) => {
      const context = gl.getContext();
      const loseContext = context.getExtension("WEBGL_lose_context");
      // R3F also releases the context during teardown. Make that release
      // idempotent when the browser has already lost it or lacks the extension.
      gl.forceContextLoss = () => { if (!context.isContextLost()) loseContext?.loseContext(); };
      const lost = (event: Event) => { event.preventDefault(); props.onFailure(); };
      gl.domElement.addEventListener("webglcontextlost", lost);
      cleanup.current = () => gl.domElement.removeEventListener("webglcontextlost", lost);
    }}>
    <PerformanceMonitor onDecline={() => setMaxDpr(1)} onFallback={() => setMaxDpr(1)} flipflops={1} />
    <SceneContents {...props} />
  </Canvas>;
}
