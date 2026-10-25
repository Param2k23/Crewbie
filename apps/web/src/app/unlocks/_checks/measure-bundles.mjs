// Run from apps/web after npm run build.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { resolve } from "node:path";

const build = resolve(".next");
const app = JSON.parse(readFileSync(resolve(build, "app-build-manifest.json"), "utf8"));
const dynamic = JSON.parse(readFileSync(resolve(build, "react-loadable-manifest.json"), "utf8"));
const initial = [...new Set([...app.pages["/layout"], ...app.pages["/unlocks/page"]])].filter((file) => file.endsWith(".js"));
const scene = Object.entries(dynamic).find(([key]) => key.includes("UnlockSceneLoader"))[1].files.filter((file) => file.endsWith(".js"));
const sizes = (files) => files.map((file) => {
  const buffer = readFileSync(resolve(build, file));
  return { file, bytes: buffer.length, gzipBytes: gzipSync(buffer, { level: 9 }).length };
});
const total = (files) => ({
  bytes: files.reduce((sum, file) => sum + file.bytes, 0),
  gzipBytes: files.reduce((sum, file) => sum + file.gzipBytes, 0),
  files,
});
console.log(JSON.stringify({ compression: "gzip-level-9", initial: total(sizes(initial)), deferred3D: total(sizes(scene)) }, null, 2));
