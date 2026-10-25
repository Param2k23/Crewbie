// Run against the integrated API and a running production Next server.
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const api = process.env.CREWBIE_SMOKE_API || "http://127.0.0.1:8788";
const web = process.env.CREWBIE_SMOKE_WEB || "http://localhost:3000";
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const evidence = new URL("../../../docs/integration/screenshots/", import.meta.url);
await mkdir(evidence, { recursive: true });
try {
  await page.goto(`${web}/arena?mode=live&view=2d`);
  await page.getByLabel("API base URL").fill(api);
  await page.getByRole("button", { name: "Start weekend", exact: true }).click();
  await page.getByText("Pending approvals", { exact: true }).first().waitFor({ timeout: 15000 });
  const sid = await page.getByLabel("Session id", { exact: true }).inputValue();
  let s = await (await fetch(`${api}/v1/sessions/${sid}/snapshot`)).json();
  if (s.state !== "approval_pending") throw new Error("backend not pending");
  await page.getByText(s.plan.title, { exact: true }).first().waitFor();
  await page.screenshot({ path: new URL("01-backend-weekend-pending.png", evidence).pathname.replace(/^\/(\w:)/, "$1"), fullPage: true });
  for (const member of ["stu_alex", "stu_maya", "stu_jordan", "stu_taylor"]) {
    const response = await fetch(`${api}/v1/sessions/${sid}/messages`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ member_ref: member, text: `I accept version ${s.version}`, version: s.version,
        request_id: `browser_accept_${member}`, synthetic_confirmed: true }) });
    if (!response.ok) throw new Error("approval failed");
  }
  await page.getByText("Confirmed", { exact: true }).first().waitFor({ timeout: 15000 });
  await page.screenshot({ path: new URL("02-backend-confirmed.png", evidence).pathname.replace(/^\/(\w:)/, "$1"), fullPage: true });
  await page.getByRole("combobox", { name: /Synthetic profile/ }).selectOption("stu_jordan");
  await page.getByLabel("New hard cap", { exact: false }).fill("20");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Send change request", exact: true }).click();
  await page.getByText("Reflected in the event stream", { exact: true }).waitFor({ timeout: 15000 });
  s = await (await fetch(`${api}/v1/sessions/${sid}/snapshot`)).json();
  if (s.state === "confirmed" || s.commitments?.accepted_count !== 0) throw new Error("approvals not invalidated");
  await page.getByText("Pending approvals", { exact: true }).first().waitFor();
  await page.screenshot({ path: new URL("03-backend-replanned.png", evidence).pathname.replace(/^\/(\w:)/, "$1"), fullPage: true });
  if (errors.length) throw new Error(errors.join("\n"));
  const report = { mode: "DEMO/SYNTHETIC; actual modules and HTTP/SSE; mock chat delivery", session_id: sid,
    final_state: s.state, final_version: s.version, accepted_count: s.commitments.accepted_count, page_errors: errors };
  await writeFile(new URL("../browser-smoke.json", evidence), JSON.stringify(report, null, 2) + "\n");
  console.log(JSON.stringify(report));
} finally { await browser.close(); }
