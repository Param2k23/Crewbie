"""Standalone read-only SSE server (stdlib only) for local demos and integration rehearsal.

    python -m services.realtime.dev_server --replay --interval 1.5

* ``GET /v1/sessions/{id}/events``  SSE, honours Last-Event-ID.
* ``POST /v1/sessions/{id}/constraint-changes``  always answers 501: the negotiation engine
  (Agent 04) owns that route. This server never fabricates a consequence of a judge request.
"""
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .replay import DEFAULT_FIXTURE, load_fixture_events, replay
from .sink import MemoryEventSink
from .sse import stream_session

_EVENTS = re.compile(r"^/v1/sessions/([A-Za-z0-9_.:-]{1,64})/events$")
_JUDGE = re.compile(r"^/v1/sessions/([A-Za-z0-9_.:-]{1,64})/constraint-changes$")


def make_handler(sink: MemoryEventSink, allowed_origins: set[str], stop: threading.Event):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):  # keep demo output quiet
            pass

        def _cors(self):
            origin = self.headers.get("Origin")
            if origin and origin in allowed_origins:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Headers", "content-type, idempotency-key, last-event-id")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _json(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self):
            if self.path == "/healthz":
                return self._json(200, {"ok": True})
            m = _EVENTS.match(self.path)
            if not m:
                return self._json(404, {"error": "NOT_FOUND"})
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                for frame in stream_session(sink, m.group(1), self.headers.get("Last-Event-ID"), stop, keepalive=10.0):
                    self.wfile.write(frame)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_POST(self):
            # Drain (bounded) so keep-alive connections stay in sync; the body is never interpreted.
            self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 65536))
            if _JUDGE.match(self.path):
                return self._json(501, {"error": "NOT_IMPLEMENTED", "detail": "constraint changes are handled by the negotiation engine; this server is a read-only event bridge"})
            self._json(404, {"error": "NOT_FOUND"})

    return Handler


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--cors-origin", action="append", default=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3100"])
    ap.add_argument("--replay", action="store_true", help="replay the canonical agent_events.json fixture")
    ap.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    ap.add_argument("--interval", type=float, default=1.5, help="seconds between replayed events (0 = emit all immediately)")
    args = ap.parse_args(argv)

    sink = MemoryEventSink()
    stop = threading.Event()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(sink, set(args.cors_origin), stop))
    if args.replay:
        from pathlib import Path

        threading.Thread(target=replay, args=(sink, load_fixture_events(Path(args.fixture)), args.interval, stop), daemon=True).start()
    print(f"realtime bridge on http://{args.host}:{args.port}  (replay={'on' if args.replay else 'off'})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
