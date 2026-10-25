"""Local synthetic integration API, reusing A6's SSE transport. Stdlib only."""
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import ThreadingHTTPServer

from services.realtime.dev_server import make_handler as realtime_handler
from services.api.runtime import Runtime, BoundaryError

ORIGINS = {"http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3100"}
ROUTE = re.compile(r"^/v1/sessions/([A-Za-z0-9_.:-]{1,64})/(snapshot|messages|constraint-changes|events)$")


def make_handler(runtime, stop):
    base = realtime_handler(runtime.events.sink, ORIGINS, stop)

    class Handler(base):
        def _allowed(self):
            # Loopback sandbox only; block browser cross-site writes and DNS rebinding.
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in {"127.0.0.1", "localhost"} and self.headers.get("Origin") in ORIGINS | {None}

        def do_GET(self):
            if not self._allowed():
                return self._json(403, {"error": "LOCAL_SANDBOX_ONLY"})
            if self.path == "/healthz":
                return self._json(200, {"ok": True, "mode": "DEMO/SYNTHETIC", "durable": False})
            if self.path == "/v1/opportunities":
                return self._json(200, {"mode": "DEMO/SYNTHETIC", "opportunities": runtime.catalog.list_opportunities(
                    "Tempe", "2026-10-26T12:00:00-07:00", "2026-10-26T14:00:00-07:00", False)})
            m = ROUTE.fullmatch(self.path)
            if m and m[1] in runtime.sessions:
                if m[2] == "snapshot":
                    with runtime.lock:
                        return self._json(200, runtime.snapshot(m[1]))
                if m[2] == "events":
                    return super().do_GET()
            return self._json(404, {"error": "NOT_FOUND"})

        def do_POST(self):
            self.close_connection = True
            if not self._allowed():
                return self._json(403, {"error": "LOCAL_SANDBOX_ONLY"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16384 or self.headers.get("Transfer-Encoding"):
                    return self._json(413, {"error": "INVALID_BODY_SIZE"})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise BoundaryError("INVALID_REQUEST")
                if self.path == "/v1/demo/sessions":
                    if body.get("synthetic_confirmed") is not True:
                        raise BoundaryError("SYNTHETIC_ONLY")
                    result = runtime.seed(body.get("scenario"), request_id=body.get("request_id"),
                        matching=body.get("matching_opt_in", False), sharing=body.get("sharing_opt_in", False),
                        introduction=body.get("introduction_opt_in", False))
                    return self._json(201, result)
                m = ROUTE.fullmatch(self.path)
                if not m or m[1] not in runtime.sessions:
                    return self._json(404, {"error": "NOT_FOUND"})
                if m[2] == "constraint-changes":
                    if body.get("session_id", m[1]) != m[1]:
                        raise BoundaryError("INVALID_REQUEST")
                    key = self.headers.get("Idempotency-Key")
                    if key and key != body.get("request_id"):
                        raise BoundaryError("REQUEST_ID_CONFLICT")
                    return self._json(202, runtime.change(m[1], body))
                if m[2] == "messages":
                    if body.get("synthetic_confirmed") is not True:
                        raise BoundaryError("SYNTHETIC_ONLY")
                    if not isinstance(body.get("text"), str) or not isinstance(body.get("request_id"), str) or not body["request_id"]:
                        raise BoundaryError("INVALID_REQUEST")
                    # Demo impersonation is intentional and never a production identity path.
                    return self._json(200, runtime.message(m[1], body.get("member_ref"), body["text"],
                        body["request_id"], version=body.get("version")))
                return self._json(404, {"error": "NOT_FOUND"})
            except (ValueError, KeyError, TypeError) as e:
                return self._json(400, {"error": getattr(e, "code", "INVALID_REQUEST")})
            except Exception:
                return self._json(503, {"error": "PROVIDER_UNAVAILABLE"})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--seed", choices=("unlocks", "evening", "weekend"), default="evening")
    args = parser.parse_args()
    runtime = Runtime()
    snap = runtime.seed(args.seed, matching=True, sharing=True, introduction=True)
    stop = threading.Event()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(runtime, stop))
    print(f"DEMO/SYNTHETIC API http://127.0.0.1:{args.port}; session={snap['session_id']}; mock delivery, no bookings", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
