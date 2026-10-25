import { CanvasTexture, SRGBColorSpace } from "three";
import type { ScenePalette } from "./sceneTypes";

export function makeCardTexture(label: string, index: number, palette: ScenePalette) {
  const canvas = document.createElement("canvas");
  canvas.width = 768; canvas.height = 480;
  const context = canvas.getContext("2d")!;
  const foreground = index === 0 ? palette.surface : palette.ink;
  context.fillStyle = index === 0 ? palette.accent : palette.surface;
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = foreground;
  context.font = "600 23px " + palette.font;
  context.fillText("ILLUSTRATIVE / " + String(index + 1).padStart(2, "0"), 45, 65);
  context.font = "800 62px " + palette.font;
  const words = label.split(" ");
  context.fillText(words[0]!, 45, 205);
  context.fillText(words.slice(1).join(" "), 45, 280);
  context.globalAlpha = .7;
  context.fillRect(45, 350, 678, 2);
  context.font = "500 20px " + palette.font;
  context.fillText("CHECK ELIGIBILITY & TERMS", 45, 400);
  context.fillText("CUBBIE × CREWBIE", 45, 438);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 2;
  return texture;
}

export function makeGlowTexture(palette: ScenePalette) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 128;
  const context = canvas.getContext("2d")!;
  const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
  gradient.addColorStop(0, palette.accent);
  gradient.addColorStop(1, "transparent");
  context.fillStyle = gradient;
  context.fillRect(0, 0, 128, 128);
  return new CanvasTexture(canvas);
}
