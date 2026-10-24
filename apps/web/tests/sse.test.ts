import { describe, expect, it } from "vitest";
import { connectSse, EventSourceLike, normalizeBaseUrl } from "@/lib/adapters/sse";

class FakeES implements EventSourceLike {
  listeners: Record<string, (e: MessageEvent) => void> = {};
  onopen: ((e: Event) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  readyState = 0;
  closed = false;
  constructor(public url: string) {}
  addEventListener(t: string, fn: (e: MessageEvent) => void) { this.listeners[t] = fn; }
  close() { this.closed = true; }
  push(data: string, type = "agent_event") { this.listeners[type]?.({ data } as MessageEvent); }
}

describe("connectSse", () => {
  it("connects read-only to the session events URL and forwards parsed frames", () => {
    let es!: FakeES; const got: unknown[] = []; const st: string[] = []; let bad = 0;
    const stop = connectSse("http://h:1", "session one", { onEvent: (e) => got.push(e), onStatus: (s) => st.push(s), onMalformed: () => bad++ }, (u) => (es = new FakeES(u)));
    expect(es.url).toBe("http://h:1/v1/sessions/session%20one/events");
    es.onopen?.(new Event("open"));
    es.push('{"a":1}');
    es.push("not json");
    es.readyState = 0; es.onerror?.(new Event("error"));
    expect(got).toEqual([{ a: 1 }]);
    expect(bad).toBe(1);
    expect(st).toEqual(["connecting", "open", "reconnecting"]);
    stop();
    expect(es.closed).toBe(true);
  });
});

describe("normalizeBaseUrl", () => {
  it("accepts http(s) only", () => {
    expect(normalizeBaseUrl("http://localhost:8787/")).toBe("http://localhost:8787");
    expect(normalizeBaseUrl("javascript:alert(1)")).toBeNull();
    expect(normalizeBaseUrl("file:///etc/passwd")).toBeNull();
    expect(normalizeBaseUrl("nonsense")).toBeNull();
  });
});
