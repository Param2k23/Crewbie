// Drives the running app (BASE_URL, default http://localhost:3100) and writes demo evidence to
// docs/mission-control/screenshots. Requires: npx playwright install chromium
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const BASE = process.env.BASE_URL ?? "http://localhost:3100";
const out = resolve(dirname(fileURLToPath(import.meta.url)), "../../../docs/mission-control/screenshots");
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const errors = [];
async function page(url, w = 1440, h = 900) {
  const p = await browser.newPage({ viewport: { width: w, height: h } });
  p.on("console", (m) => m.type() === "error" && !/501 \(Not Implemented\)/.test(m.text()) && errors.push(`${url}: ${m.text()}`));
  p.on("pageerror", (e) => errors.push(`${url}: ${e.message}`));
  await p.goto(BASE + url, { waitUntil: "networkidle" });
  return p;
}
const shot = async (p, name) => { await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(250); await p.screenshot({ path: `${out}/${name}.png` }); };
const step = async (p, n) => { for (let i = 0; i < n; i++) { await p.getByRole("button", { name: /Step/ }).click(); await p.waitForTimeout(150); } };

// 1. Campus Pulse
let p = await page("/");
await shot(p, "01-campus-pulse");

// 2. Demo: rejection -> pending -> judge
p = await page("/arena?mode=demo&view=3d");
await p.waitForSelector("canvas", { timeout: 15000 });
await step(p, 3); await p.waitForTimeout(800);
await shot(p, "02-demo-proposal-rejected");
await step(p, 7); await p.waitForTimeout(800);
await shot(p, "03-demo-pending-conditional-approvals");

await p.getByLabel("This targets a synthetic sandbox profile").check();
await p.getByLabel(/New hard cap/).fill("45");
await p.getByRole("button", { name: "Send change request" }).click();
await p.waitForTimeout(150);
await shot(p, "04-judge-request-pending");
await p.getByText(/Server: accepted/).waitFor({ timeout: 5000 });
await p.getByLabel("Speed").selectOption("4");
await p.getByText(/Approvals for v3: 0 \/ 4/).waitFor({ timeout: 15000 });
await p.waitForTimeout(900);
await shot(p, "05-judge-replanned-v3-approvals-reset");

// 3. Honest failure: cap below any feasible plan
p = await page("/arena?mode=demo&view=3d");
await p.waitForSelector("canvas");
await step(p, 10);
await p.getByLabel("This targets a synthetic sandbox profile").check();
await p.getByLabel(/New hard cap/).fill("20");
await p.getByRole("button", { name: "Send change request" }).click();
await p.getByLabel("Speed").selectOption("4");
await p.getByText(/No feasible plan/).first().waitFor({ timeout: 15000 });
await p.waitForTimeout(900);
await shot(p, "06-judge-no-feasible-plan");

// 4. Confirmed (canonical fixture, full replay)
p = await page("/arena?mode=fixture&view=3d");
await p.waitForSelector("canvas");
await p.getByLabel("Speed").selectOption("8").catch(() => {});
await step(p, 11); await p.waitForTimeout(900);
await shot(p, "07-fixture-confirmed");

// 5. 2D fallback of the demo pending state
p = await page("/arena?mode=demo&view=2d");
await step(p, 10);
await shot(p, "08-2d-fallback-pending");

// 6. Narrow laptop/tablet width
p = await page("/arena?mode=demo&view=2d", 820, 1100);
await step(p, 10);
await shot(p, "09-narrow-2d");

// 7. Live SSE bridge (optional): LIVE_API=http://127.0.0.1:8787 with `python -m services.realtime.dev_server --replay`
if (process.env.LIVE_API) {
  p = await page("/arena?mode=live&view=3d");
  await p.getByLabel("API base URL").fill(process.env.LIVE_API);
  await p.getByRole("button", { name: "Connect" }).click();
  await p.getByText("Stream: open").waitFor({ timeout: 10000 });
  await p.locator(".timeline").getByText("Backend confirmed plan v2").waitFor({ timeout: 40000 });
  await p.waitForTimeout(900);
  await shot(p, "10-live-sse-confirmed");
  // Judge request against the read-only bridge must fail honestly (HTTP 501)
  await p.getByLabel("This targets a synthetic sandbox profile").check();
  await p.getByRole("button", { name: "Send change request" }).click();
  await p.getByText(/Server: unavailable/).waitFor({ timeout: 5000 });
  await p.getByText(/Server: unavailable/).scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${out}/11-live-judge-honest-failure.png` });
}

await browser.close();
if (errors.length) { console.log("CONSOLE ERRORS:\n" + errors.join("\n")); process.exitCode = 1; } else console.log("screenshots ok, no console errors");
