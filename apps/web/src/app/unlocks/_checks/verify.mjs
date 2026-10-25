// Run from apps/web against a production server on PORT (default 3100).
import { chromium } from "playwright";
import { strict as assert } from "node:assert";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFileSync } from "node:fs";

const base = `http://127.0.0.1:${process.env.PORT || 3100}`;
const browser = await chromium.launch({ channel: "msedge", headless: true,
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const errors = [];
const upstreamWarnings = [];
const loadable = JSON.parse(readFileSync(".next/react-loadable-manifest.json", "utf8"));
const sceneFiles = Object.entries(loadable).find(([key]) => key.includes("UnlockSceneLoader"))[1].files;
async function open(options = {}, cores = 8) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, ...options });
  await page.addInitScript((cores) => Object.defineProperty(navigator, "hardwareConcurrency", { get: () => cores }), cores);
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "warning" && message.text() === "THREE.Clock: This module has been deprecated. Please use THREE.Timer instead.") upstreamWarnings.push(message.text());
    else if (message.type() === "error" || message.type() === "warning") errors.push(message.text());
  });
  await page.goto(base + "/unlocks", { waitUntil: "networkidle" });
  return page;
}
async function opacity(page, selector) {
  return page.locator(selector).evaluateAll((nodes) => nodes.map((node) => Number(getComputedStyle(node).opacity)));
}
try {
  const page = await open();
  await page.waitForSelector('[data-scene-ready="true"]', { timeout: 45000 });
  await page.waitForFunction(() => Number(document.querySelector('[data-crewbie-unlocks]').dataset.sceneDrawCalls) > 0);
  await page.waitForTimeout(1500);
  assert.equal(await page.locator(".pin-spacer").count(), 0);
  assert.equal(await page.locator("section").count(), 6);
  assert.equal(await page.locator("body > header.sitenav").isVisible(), false);
  assert.equal(await page.locator("canvas").count(), 1);
  assert.equal(await page.locator("[data-scene-active]").evaluate((node) => getComputedStyle(node).position), "fixed");
  const calls = await page.locator("[data-scene-draw-calls]").getAttribute("data-scene-draw-calls");
  assert(Number(calls) > 0 && Number(calls) < 100, `Draw calls: ${calls}`);
  await page.screenshot({ path: join(tmpdir(), "crewbie-rich-hero.png") });
  const cta = page.locator("[data-cta]").first();
  const box = await cta.boundingBox();
  await page.mouse.move(box.x + box.width * .8, box.y + box.height * .6);
  await page.waitForTimeout(600);
  assert.notEqual(await cta.evaluate((node) => getComputedStyle(node).transform), "none");
  await cta.click();
  await page.waitForTimeout(1200);
  assert((await page.locator("[data-planning-panel]").boundingBox()).y < 1000);
  await page.waitForFunction(() => Number(document.querySelector("[data-example-index]").textContent) >= 2, { timeout: 20000 });
  await page.waitForFunction(() => Number(document.querySelector("[data-example-index]").textContent) === 3, { timeout: 20000 });
  console.log("PASS: time-based panel cycles through three illustrative requests without scrolling.");
  await page.locator("[data-planning-panel]").scrollIntoViewIfNeeded();
  await page.waitForTimeout(5300);
  await page.screenshot({ path: join(tmpdir(), "crewbie-rich-plan.png") });
  await page.locator("footer").scrollIntoViewIfNeeded();
  await page.waitForTimeout(1000);
  const frozen = await page.locator("[data-crewbie-unlocks]").getAttribute("data-scene-frames");
  const example = await page.locator("[data-example-index]").textContent();
  const blob = await page.locator("[data-blob]").first().evaluate((node) => getComputedStyle(node).transform);
  await page.waitForTimeout(2200);
  assert.equal(await page.locator("[data-crewbie-unlocks]").getAttribute("data-scene-frames"), frozen);
  assert.equal(await page.locator("[data-example-index]").textContent(), example);
  assert.equal(await page.locator("[data-blob]").first().evaluate((node) => getComputedStyle(node).transform), blob);
  console.log(`PASS: ${calls} draw calls; canvas, planning replay and ambient loops pause off-screen.`);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.waitForTimeout(500);
  assert.equal(await page.locator("canvas").count(), 0);
  assert((await opacity(page, "[data-plan-line]")).every((value) => value === 1));
  assert.equal((await opacity(page, "[data-hero-composition] > [data-tilt]")).at(0), 1);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.locator("header a").filter({ hasText: "How it works" }).count();
  // Real Next Link client-side unmount: restore the inherited header and remove Lenis.
  await page.locator('body > header.sitenav a[href="/"]').first().evaluate((node) => node.click());
  await page.waitForURL(base + "/");
  assert(await page.locator("body > header.sitenav").isVisible());
  assert.equal(await page.locator("canvas").count(), 0);
  assert.equal(await page.evaluate(() => document.documentElement.classList.contains("lenis")), false);
  await page.goBack({ waitUntil: "networkidle" });
  await page.waitForSelector("[data-crewbie-unlocks]");
  assert.equal(await page.locator("body > header.sitenav").isVisible(), false);
  await page.close();

  const mobile = await open({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await mobile.waitForSelector('[data-scene-mode="mobile"]', { timeout: 45000 });
  await mobile.locator('[data-hero-composition]').scrollIntoViewIfNeeded();
  await mobile.waitForTimeout(1000);
  await mobile.screenshot({ path: join(tmpdir(), "crewbie-rich-mobile-hero.png") });
  assert.equal(await mobile.evaluate(() => document.documentElement.classList.contains("lenis")), false);
  assert(await mobile.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await mobile.locator("[data-planning-panel]").scrollIntoViewIfNeeded();
  await mobile.waitForFunction(() => Number(document.querySelector("[data-example-index]").textContent) >= 2, { timeout: 20000 });
  await mobile.locator("footer").scrollIntoViewIfNeeded();
  await mobile.waitForTimeout(1200);
  await mobile.screenshot({ path: join(tmpdir(), "crewbie-rich-mobile.png"), fullPage: true });
  await mobile.close();

  const low = await open({}, 2);
  await low.waitForTimeout(900);
  assert.equal(await low.locator("canvas").count(), 0);
  assert.equal(await low.locator("[data-ambient-off]").count(), 1);
  assert(!(await low.evaluate((files) => performance.getEntriesByType("resource").some((entry) => files.some((file) => entry.name.endsWith(file))), sceneFiles)));
  await low.close();
  const lost = await open();
  await lost.waitForSelector('[data-scene-ready="true"]', { timeout: 45000 });
  await lost.locator("canvas").evaluate((canvas) => canvas.getContext("webgl2").getExtension("WEBGL_lose_context").loseContext());
  await lost.waitForFunction(() => !document.querySelector("canvas"));
  assert.equal((await opacity(lost, "[data-hero-composition] > [data-tilt]")).at(0), 1);
  await lost.close();
  const unsupported = await browser.newPage();
  await unsupported.addInitScript(() => {
    Object.defineProperty(navigator, "hardwareConcurrency", { get: () => 8 });
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
      if (kind === "webgl2" || kind === "webgl") return null;
      return getContext.call(this, kind, ...args);
    };
  });
  unsupported.on("pageerror", (error) => errors.push(error.message));
  await unsupported.goto(base + "/unlocks", { waitUntil: "networkidle" });
  assert.equal(await unsupported.locator("canvas").count(), 0);
  assert.equal((await opacity(unsupported, "[data-hero-composition] > [data-tilt]")).at(0), 1);
  await unsupported.close();
  const reduced = await open({ reducedMotion: "reduce" });
  assert.equal(await reduced.locator("canvas").count(), 0);
  assert((await opacity(reduced, "[data-plan-line]")).every((value) => value === 1));
  await reduced.close();
  const noJS = await open({ javaScriptEnabled: false });
  assert.equal(await noJS.locator("section").count(), 6);
  assert(await noJS.locator("[data-planning-panel]").isVisible());
  assert.equal(await noJS.locator("body > header.sitenav").isVisible(), false);
  await noJS.close();
  assert.deepEqual(errors, []);
  console.log("Known upstream warnings (not suppressed in the app):", upstreamWarnings);
  console.log("PASS: mobile scene/replay, reduced-motion static panel, low-power/unsupported-WebGL/context-loss fallbacks, no-JS, SPA cleanup and browser console.");
} finally { await browser.close(); }
