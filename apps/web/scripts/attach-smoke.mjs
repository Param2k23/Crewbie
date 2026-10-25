// Read-only check against an EXISTING session. Send an approval in Discord while it waits.
// CREWBIE_SMOKE_SESSION=session_... node scripts/attach-smoke.mjs
import assert from "node:assert/strict";
import { chromium } from "playwright";

const session = process.env.CREWBIE_SMOKE_SESSION;
assert(session, "Set CREWBIE_SMOKE_SESSION to the existing Discord session id");
const api = process.env.CREWBIE_SMOKE_API || "http://127.0.0.1:8787";
const web = process.env.CREWBIE_SMOKE_WEB || "http://localhost:3000";
const timeout = Number(process.env.CREWBIE_SMOKE_TIMEOUT || 60000);
const snapshotUrl = `${api}/v1/sessions/${session}/snapshot`;
const initial = await (await fetch(snapshotUrl)).json();
assert.equal(initial.session_id, session);
const browser = await chromium.launch({ headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const errors = [];
try {
  const pages = [];
  for (const view of ["2d", "3d"]) {
    const page = await browser.newPage();
    page.on("pageerror", error => errors.push(error.message));
    // Attachment and subscription must never create or modify a session.
    await page.route(`${api}/**`, async route => {
      if (route.request().method() !== "GET") {
        errors.push(`Unexpected write: ${route.request().url()}`);
        await route.abort();
      } else await route.continue();
    });
    await page.goto(`${web}/arena?mode=live&view=${view}`);
    await page.getByLabel("API base URL").fill(` ${api}/ `);
    await page.getByLabel("Session id", { exact: true }).fill(` ${session} `);
    const stream = page.waitForResponse(r => r.url() === `${api}/v1/sessions/${session}/events`);
    await page.getByRole("button", { name: "Connect", exact: true }).click();
    assert.equal((await stream).status(), 200);
    await page.getByRole("img", { name: view === "2d" ? /2D negotiation view/ : "3D negotiation arena" }).waitFor();
    await page.waitForFunction(count => document.querySelector('[aria-label="Accepted approvals"]')?.getAttribute("aria-valuenow") === String(count), initial.commitments.accepted_count);
    pages.push(page);
    console.log(`${view}: attached ${session}, v${initial.version}, ${initial.commitments.accepted_count}/${initial.required_count}`);
  }
  console.log("Waiting for an approval from a pending member in Discord…");
  await pages[0].waitForFunction(count => Number(document.querySelector('[aria-label="Accepted approvals"]')?.getAttribute("aria-valuenow")) > count, initial.commitments.accepted_count, { timeout });
  const updated = await (await fetch(snapshotUrl)).json();
  assert.equal(updated.session_id, session);
  assert.equal(updated.version, initial.version);
  for (const page of pages) {
    await page.waitForFunction(count => document.querySelector('[aria-label="Accepted approvals"]')?.getAttribute("aria-valuenow") === String(count), updated.commitments.accepted_count);
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ session_id: session, version: updated.version, before: initial.commitments.accepted_count, after: updated.commitments.accepted_count, views: ["2d", "3d"], writes: 0 }));
} finally {
  await browser.close();
}
