// Copies the canonical, read-only fixtures into src/lib/fixtures so the app
// runs offline without reaching outside apps/web. tests/fixtures.test.ts fails
// if the copies drift from docs/implementation/fixtures.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../../docs/implementation/fixtures");
const dst = resolve(here, "../src/lib/fixtures");
mkdirSync(dst, { recursive: true });
for (const f of ["agent_events.json", "opportunities.json", "scenarios.json"]) {
  copyFileSync(resolve(src, f), resolve(dst, f));
  console.log("synced", f);
}
