"use client";

import { createContext, useContext, type MutableRefObject } from "react";

export type SceneMotion = {
  progress: number;
  hero: number;
  pointer: { x: number; y: number };
  anchor: { x: number; y: number };
};
export const SceneMotionContext = createContext<MutableRefObject<SceneMotion> | null>(null);
export function useSceneMotion() {
  const state = useContext(SceneMotionContext);
  if (!state) throw new Error("Unlock scene requires the route motion provider.");
  return state;
}
