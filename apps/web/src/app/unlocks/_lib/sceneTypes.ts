import type { MutableRefObject } from "react";
import type { SceneMotion } from "../_components/SceneMotion";

export type ScenePalette = { accent: string; paper: string; surface: string; ink: string; muted: string; font: string };
export type UnlockSceneProps = {
  motion: MutableRefObject<SceneMotion>;
  palette: ScenePalette;
  active: boolean;
  mobile: boolean;
  root: HTMLElement;
  onReady: () => void;
  onFailure: () => void;
};
