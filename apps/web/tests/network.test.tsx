// @vitest-environment jsdom
import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NetworkAdapter } from "@/lib/adapters";
import { MissionControlApp } from "@/components/MissionControlApp";
import { ArenaFallback } from "@/components/ArenaFallback";
import { useMissionControl } from "@/lib/useMissionControl";
import { buildSceneModel } from "@/lib/scene/model";
import { normalizeSessionId } from "@/lib/adapters/sse";
import traces from "./data/integrated-traces.json";

// Keep the form test focused on attachment, without loading WebGL.
vi.mock("@/components/MissionControl", () => ({
  MissionControl: ({ adapter }: { adapter: NetworkAdapter }) => <div>Attached {adapter.sessionId}</div>,
}));

class FakeEventSource {
  static latest: FakeEventSource;
  listeners: Record<string, (event: MessageEvent) => void> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 1;
  close = vi.fn();
  constructor(readonly url: string) { FakeEventSource.latest = this; }
  addEventListener(type: string, fn: (event: MessageEvent) => void) { this.listeners[type] = fn; }
  push(raw: unknown) { this.listeners.agent_event!({ data: JSON.stringify(raw) } as MessageEvent); }
}

afterEach(() => { vi.unstubAllGlobals(); });

describe("attach to an existing Discord session", () => {
  const id = "session_0ff1db590cb4";
  it("normalizes pasted whitespace while retaining the API's session-id restrictions", () => {
    const adapter = NetworkAdapter.create(" http://127.0.0.1:8787/// \n", ` \n${id}\t`)!;
    expect(adapter.baseUrl).toBe("http://127.0.0.1:8787");
    expect(adapter.sessionId).toBe(id);
    for (const invalid of ["", "   ", "session one", "../session", "x".repeat(65)]) {
      expect(normalizeSessionId(invalid)).toBeNull();
      expect(NetworkAdapter.create("http://127.0.0.1:8787", invalid)).toBeNull();
    }
  });

  it("Connect accepts pasted identifiers without calling the demo creation endpoint", () => {
    const fetch = vi.fn(); vi.stubGlobal("fetch", fetch);
    render(<MissionControlApp initialMode="live" />);
    fireEvent.change(screen.getByLabelText("API base URL"), { target: { value: " http://127.0.0.1:8787/ " } });
    fireEvent.change(screen.getByLabelText("Session id"), { target: { value: ` ${id} ` } });
    fireEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(screen.getByText(`Attached ${id}`)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("identifies which input failed before attempting a connection", () => {
    render(<MissionControlApp initialMode="live" />);
    fireEvent.change(screen.getByLabelText("Session id"), { target: { value: "session with spaces" } });
    fireEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid session id.");
    fireEvent.change(screen.getByLabelText("API base URL"), { target: { value: "invalid" } });
    fireEvent.click(screen.getByRole("button", { name: "Connect" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Invalid API base URL.");
  });

  it("replays existing events and delivers later approvals to the 2D view and shared 3D model", async () => {
    vi.stubGlobal("EventSource", FakeEventSource);
    const snapshot = { ...traces.evening.snapshot, session_id: id };
    const fetch = vi.fn(async (_url: string) => ({ ok: true, json: async () => snapshot }));
    vi.stubGlobal("fetch", fetch);
    const adapter = NetworkAdapter.create("http://127.0.0.1:8787/", ` ${id} `)!;
    const { result, unmount } = renderHook(() => useMissionControl(adapter));
    const es = FakeEventSource.latest;
    expect(es.url).toBe(`http://127.0.0.1:8787/v1/sessions/${id}/events`);
    const events = traces.evening.confirmed.map(e => ({ ...e, session_id: id }));
    const approvals = events.filter(e => e.type === "member_response_received" && "state" in e.payload && e.payload.state === "accepted");
    expect(approvals).toHaveLength(4);
    const before = events.slice(0, events.indexOf(approvals[2]!));
    await act(async () => { es.onopen?.(); before.forEach(e => es.push(e)); });
    expect(result.current.view.sessionId).toBe(id);
    expect(result.current.view.acceptedCount).toBe(2);
    const fallback = render(<ArenaFallback view={result.current.view} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/2 of 4/);
    await act(async () => { es.push(approvals[2]); });
    fallback.rerender(<ArenaFallback view={result.current.view} />);
    expect(screen.getByRole("img")).toHaveAccessibleName(/3 of 4/);
    const model = buildSceneModel(result.current.view);
    expect(model.nodes.filter(n => n.state === "accepted")).toHaveLength(3);
    expect(model.core.status).toBe("awaiting_approval");
    expect(result.current.view.currentVersion).toBe(snapshot.version);
    const calls = fetch.mock.calls.length;
    await act(async () => { es.onopen?.(); });
    await waitFor(() => expect(fetch.mock.calls.length).toBeGreaterThan(calls));
    expect(fetch.mock.calls.every(args => args[0] === `http://127.0.0.1:8787/v1/sessions/${id}/snapshot`)).toBe(true);
    unmount();
    expect(es.close).toHaveBeenCalledOnce();
  });
});
