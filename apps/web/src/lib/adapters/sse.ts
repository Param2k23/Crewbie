export type ConnectionStatus = "idle" | "connecting" | "open" | "reconnecting" | "closed" | "error";

export interface SseHandlers {
  onEvent: (raw: unknown) => void;
  onStatus: (s: ConnectionStatus) => void;
  /** Called for frames that are not valid JSON; payload is never echoed. */
  onMalformed: () => void;
}

/** Only http(s) origins are accepted for the live bridge. */
export function normalizeBaseUrl(input: string): string | null {
  try {
    const u = new URL(input.trim());
    if (u.protocol !== "http:" && u.protocol !== "https:") return null;
    return u.origin + u.pathname.replace(/\/+$/, "");
  } catch {
    return null;
  }
}

export interface EventSourceLike {
  addEventListener(type: string, fn: (e: MessageEvent) => void): void;
  close(): void;
  onopen: ((e: Event) => void) | null;
  onerror: ((e: Event) => void) | null;
  readyState: number;
}

/**
 * Read-only subscription to GET /v1/sessions/{id}/events. The browser's EventSource resends
 * Last-Event-ID on reconnect; duplicates are discarded by the reducer's event_id dedup.
 */
export function connectSse(
  baseUrl: string,
  sessionId: string,
  h: SseHandlers,
  factory: (url: string) => EventSourceLike = (u) => new EventSource(u) as unknown as EventSourceLike,
): () => void {
  h.onStatus("connecting");
  const es = factory(`${baseUrl}/v1/sessions/${encodeURIComponent(sessionId)}/events`);
  const handle = (e: MessageEvent) => {
    try {
      h.onEvent(JSON.parse(String(e.data)));
    } catch {
      h.onMalformed();
    }
  };
  es.onopen = () => h.onStatus("open");
  es.onerror = () => h.onStatus(es.readyState === 2 ? "closed" : "reconnecting");
  es.addEventListener("agent_event", handle);
  es.addEventListener("message", handle);
  return () => {
    es.close();
    h.onStatus("closed");
  };
}
