import { describe, expect, it } from "vitest";
import { sanitizeEvent } from "@/lib/events/sanitize";
import { ev } from "./helpers";

describe("sanitizeEvent", () => {
  it("accepts a valid event and drops unknown payload keys", () => {
    const r = sanitizeEvent(ev(1, "candidate_proposed", { plan_id: "p1", version: 1, extra_thing: "x" }));
    expect(r.ok).toBe(true);
    if (r.ok) expect(r.event.payload).toEqual({ plan_id: "p1", version: 1 });
  });
  it.each(["internal", "private", undefined, "public"])("rejects visibility %s", (v) => {
    const r = sanitizeEvent(ev(1, "negotiation_started", {}, { visibility: v }));
    expect(r).toMatchObject({ ok: false, code: "NOT_GROUP_SAFE" });
  });
  it.each([
    "hard_budget_cap_cents",
    "estimated_cost_cents_by_ref",
    "calendar_title",
    "raw_prompt",
    "access_token",
    "private_reason",
    "reasoning",
    "blocked_windows",
    "dietary_restriction",
  ])("rejects a payload leaking %s (even nested)", (key) => {
    expect(sanitizeEvent(ev(1, "candidate_proposed", { version: 1, nested: { [key]: 1 } }))).toMatchObject({ ok: false, code: "FORBIDDEN_KEY" });
  });
  it("rejects unknown types, bad ids and timestamps without timezone", () => {
    expect(sanitizeEvent(ev(1, "debug_dump"))).toMatchObject({ code: "BAD_TYPE" });
    expect(sanitizeEvent(ev(1, "negotiation_started", {}, { event_id: "<img src=x>" }))).toMatchObject({ code: "BAD_FIELD" });
    expect(sanitizeEvent(ev(1, "negotiation_started", {}, { timestamp: "2026-10-24T18:00:00" }))).toMatchObject({ code: "BAD_FIELD" });
    expect(sanitizeEvent("nope")).toMatchObject({ code: "NOT_OBJECT" });
  });
  it("strips markup from free text and bounds length", () => {
    const r = sanitizeEvent(ev(1, "counteroffer_proposed", { version: 2, summary: `<script>alert(1)</script>${"x".repeat(500)}` }));
    expect(r.ok).toBe(true);
    if (r.ok) {
      expect(r.event.payload.summary).not.toMatch(/[<>]/);
      expect(r.event.payload.summary!.length).toBeLessThanOrEqual(280);
    }
  });
  it("rejects invalid typed fields", () => {
    expect(sanitizeEvent(ev(1, "member_response_received", { member_ref: "a", state: "confirmed", version: 1 }))).toMatchObject({ code: "BAD_PAYLOAD" });
    expect(sanitizeEvent(ev(1, "candidate_proposed", { version: "1" }))).toMatchObject({ code: "BAD_PAYLOAD" });
  });
});
