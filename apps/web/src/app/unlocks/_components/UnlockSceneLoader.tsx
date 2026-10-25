"use client";

import dynamic from "next/dynamic";
import { Component, useEffect, useRef, useState, type ReactNode } from "react";
import { motion as config } from "../_lib/motion.config";
import type { ScenePalette } from "../_lib/sceneTypes";
import { useSceneMotion } from "./SceneMotion";
import styles from "../unlocks.module.css";

const UnlockScene = dynamic(() => import("./UnlockScene"), { ssr: false, loading: () => null });

class SceneBoundary extends Component<{ children: ReactNode; onFailure: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFailure(); }
  render() { return this.state.failed ? null : this.props.children; }
}

export function UnlockSceneLoader() {
  const shared = useSceneMotion();
  const holder = useRef<HTMLDivElement>(null);
  const [root, setRoot] = useState<HTMLElement | null>(null);
  const [palette, setPalette] = useState<ScenePalette | null>(null);
  const [eligible, setEligible] = useState(false);
  const [active, setActive] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const element = holder.current!.closest<HTMLElement>("[data-crewbie-unlocks]")!;
    const hero = element.querySelector<HTMLElement>("[data-hero]")!;
    setRoot(element);
    const style = getComputedStyle(element);
    const color = (name: string) => style.getPropertyValue(name).trim();
    setPalette({ accent: color("--accent"), paper: color("--paper"), surface: color("--surface"), ink: color("--ink"), muted: color("--muted"), font: color("--display") });
    const reduced = matchMedia(config.reduced);
    const narrow = matchMedia("(max-width: 899px), (pointer: coarse)");
    let painted = false;
    let visible = false;
    let supportsWebGL: boolean | undefined;
    const sync = () => {
      let allowed = painted && !reduced.matches && (navigator.hardwareConcurrency || 8) > 4;
      if (allowed && supportsWebGL === undefined) {
        // Avoid mounting R3F (and throwing a renderer error) on unsupported devices.
        const probe = document.createElement("canvas");
        const gl = probe.getContext("webgl2");
        supportsWebGL = !!gl;
        gl?.getExtension("WEBGL_lose_context")?.loseContext();
        probe.width = probe.height = 0;
      }
      allowed = allowed && supportsWebGL === true;
      setEligible(allowed);
      setMobile(narrow.matches);
      setActive(allowed && visible && !document.hidden);
    };
    // Two one-shot frames defer the dynamic import until after the static page paints.
    let paintFrame = requestAnimationFrame(() => {
      paintFrame = requestAnimationFrame(() => { painted = true; sync(); });
    });
    const observer = new IntersectionObserver(([entry]) => { visible = !!entry?.isIntersecting; sync(); });
    observer.observe(hero);
    reduced.addEventListener("change", sync);
    narrow.addEventListener("change", sync);
    document.addEventListener("visibilitychange", sync);
    return () => {
      cancelAnimationFrame(paintFrame);
      observer.disconnect();
      reduced.removeEventListener("change", sync);
      narrow.removeEventListener("change", sync);
      document.removeEventListener("visibilitychange", sync);
      element.removeAttribute("data-scene-ready");
      element.removeAttribute("data-scene-mode");
    };
  }, []);

  useEffect(() => {
    if (!eligible) setReady(false);
  }, [eligible]);

  useEffect(() => {
    if (!root) return;
    if (ready && eligible && !failed) {
      root.dataset.sceneReady = "true";
      root.dataset.sceneMode = mobile ? "mobile" : "desktop";
    } else {
      root.removeAttribute("data-scene-ready");
      root.removeAttribute("data-scene-mode");
    }
  }, [root, ready, eligible, failed, mobile]);

  const show = eligible && !failed && palette && root;
  return <div ref={holder} className={styles.sceneLayer} aria-hidden="true" data-scene-active={active} style={{ opacity: active ? 1 : 0 }}>
    {show && <SceneBoundary onFailure={() => setFailed(true)}>
      <UnlockScene motion={shared} palette={palette} root={root} active={active} mobile={mobile}
        onReady={() => setReady(true)} onFailure={() => setFailed(true)} />
    </SceneBoundary>}
  </div>;
}
