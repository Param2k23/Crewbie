"""Run from the repo root:  python -m unittest discover -s tests/realtime -t .  -v"""
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from tests.realtime import _paths  # noqa: F401  (adds repo root to sys.path)
from services.realtime import EventRejected, MemoryEventSink, format_sse, stream_session, validate_public_event
from services.realtime.dev_server import make_handler
from services.realtime.replay import load_fixture_events, replay


def ev(n, type_="candidate_proposed", payload=None, **extra):
    base = {
        "event_id": f"ev_{n:04d}", "session_id": "s1", "timestamp": f"2026-10-24T18:{n:02d}:00Z",
        "type": type_, "actor_ref": "coordination_engine", "visibility": "group_safe",
        "payload": payload if payload is not None else {"plan_id": "p1", "version": 1}, "synthetic": True,
    }
    base.update(extra)
    return base


class SchemaTests(unittest.TestCase):
    def test_fixture_events_all_valid(self):
        for e in load_fixture_events():
            self.assertEqual(validate_public_event(e)["event_id"], e["event_id"])

    def test_rejects_non_group_safe(self):
        for vis in ("internal", "private", None, "public"):
            with self.assertRaises(EventRejected) as c:
                validate_public_event(ev(1, visibility=vis))
            self.assertEqual(c.exception.code, "NOT_GROUP_SAFE")

    def test_rejects_private_keys_even_nested(self):
        for key in ("hard_budget_cap_cents", "estimated_cost_cents_by_ref", "calendar_title", "raw_prompt", "access_token", "reasoning", "blocked_windows", "diet_reason"):
            with self.assertRaises(EventRejected) as c:
                validate_public_event(ev(1, payload={"version": 1, "x": {key: 1}}))
            self.assertEqual(c.exception.code, "FORBIDDEN_KEY", key)

    def test_unknown_payload_keys_dropped_and_text_cleaned(self):
        out = validate_public_event(ev(1, "counteroffer_proposed", {"version": 2, "mystery": "x", "summary": "<b>hi</b>\n there"}))
        self.assertEqual(out["payload"], {"version": 2, "summary": "b hi /b there"})

    def test_bad_fields(self):
        with self.assertRaises(EventRejected):
            validate_public_event(ev(1, "debug_dump"))
        with self.assertRaises(EventRejected):
            validate_public_event(ev(1, timestamp="2026-10-24T18:00:00"))
        with self.assertRaises(EventRejected):
            validate_public_event(ev(1, payload={"version": True}))
        with self.assertRaises(EventRejected):
            validate_public_event(ev(1, "member_response_received", {"member_ref": "a", "state": "confirmed"}))


class SinkTests(unittest.TestCase):
    def test_dedup_order_and_rejection_count(self):
        s = MemoryEventSink()
        s.emit(ev(1)); s.emit(ev(2)); s.emit(ev(1))
        self.assertEqual([e["event_id"] for e in s.events("s1")], ["ev_0001", "ev_0002"])
        with self.assertRaises(EventRejected):
            s.emit(ev(3, visibility="internal"))
        self.assertEqual(s.rejected, ["NOT_GROUP_SAFE"])
        self.assertEqual(len(s.events("s1")), 2)

    def test_private_event_never_stored(self):
        s = MemoryEventSink()
        with self.assertRaises(EventRejected):
            s.emit(ev(1, payload={"hard_budget_cap_cents": 6000}))
        self.assertEqual(s.events("s1"), [])

    def test_read_after_last_event_id(self):
        s = MemoryEventSink()
        for i in (1, 2, 3):
            s.emit(ev(i))
        self.assertEqual([e["event_id"] for e in s.read_after("s1", "ev_0002")], ["ev_0003"])
        self.assertEqual(len(s.read_after("s1", "unknown")), 3)  # client de-dups
        self.assertEqual(s.read_after("s1", "ev_0003"), [])

    def test_sessions_are_isolated(self):
        s = MemoryEventSink()
        s.emit(ev(1)); s.emit(ev(2, session_id="s2"))
        self.assertEqual(len(s.events("s1")), 1)
        self.assertEqual(len(s.events("s2")), 1)

    def test_replay_paces_without_inventing(self):
        s = MemoryEventSink()
        sleeps = []
        n = replay(s, load_fixture_events(), interval=0.5, sleep=sleeps.append)
        self.assertEqual(n, 11)
        self.assertEqual(len(s.events("session_trip_001")), 11)
        self.assertEqual(sleeps, [0.5] * 11)


class SseFormatTests(unittest.TestCase):
    def test_frame_shape(self):
        frame = format_sse(validate_public_event(ev(7))).decode()
        self.assertTrue(frame.startswith("id: ev_0007\nevent: agent_event\ndata: {"))
        self.assertTrue(frame.endswith("\n\n"))
        self.assertNotIn("\n", frame.split("data: ", 1)[1].rstrip("\n"))

    def test_stream_resumes_and_keeps_alive(self):
        s = MemoryEventSink()
        for i in (1, 2, 3):
            s.emit(ev(i))
        it = stream_session(s, "s1", "ev_0001", keepalive=0.05)
        self.assertEqual(next(it), b"retry: 2000\n\n")
        ids = [next(it).decode().split("\n", 1)[0] for _ in range(2)]
        self.assertEqual(ids, ["id: ev_0002", "id: ev_0003"])
        self.assertEqual(next(it), b": keep-alive\n\n")


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sink = MemoryEventSink()
        for e in load_fixture_events():
            cls.sink.emit(e)
        cls.stop = threading.Event()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.sink, {"http://localhost:3000"}, cls.stop))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.stop.set()
        cls.server.shutdown()
        cls.server.server_close()

    def _read_frames(self, headers, want):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", "/v1/sessions/session_trip_001/events", headers=headers)
        r = c.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(r.getheader("Content-Type"), "text/event-stream")
        ids, buf = [], b""
        while len(ids) < want:
            buf += r.read1(4096)
            ids = [l[4:] for l in buf.decode().splitlines() if l.startswith("id: ")]
        c.close()
        return r, ids

    def test_streams_all_events_in_order(self):
        r, ids = self._read_frames({}, 11)
        self.assertEqual(ids[:3], ["ev_0001", "ev_0002", "ev_0003"])
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), None)

    def test_last_event_id_resume(self):
        _, ids = self._read_frames({"Last-Event-ID": "ev_0009"}, 2)
        self.assertEqual(ids, ["ev_0010", "ev_0011"])

    def test_cors_only_for_allowed_origin(self):
        r, _ = self._read_frames({"Origin": "http://localhost:3000"}, 1)
        self.assertEqual(r.getheader("Access-Control-Allow-Origin"), "http://localhost:3000")
        r, _ = self._read_frames({"Origin": "https://evil.example"}, 1)
        self.assertIsNone(r.getheader("Access-Control-Allow-Origin"))

    def test_bridge_is_read_only_and_judge_route_is_honestly_unimplemented(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("POST", "/v1/sessions/session_trip_001/constraint-changes", body="{}", headers={"Content-Type": "application/json"})
        r = c.getresponse()
        self.assertEqual(r.status, 501)
        self.assertEqual(json.loads(r.read())["error"], "NOT_IMPLEMENTED")
        c.request("POST", "/v1/sessions/session_trip_001/events", body=json.dumps(ev(99)))
        r = c.getresponse(); r.read()
        self.assertEqual(r.status, 404)
        self.assertEqual(len(self.sink.events("session_trip_001")), 11)  # nothing was written

    def test_invalid_session_id_not_routed(self):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", "/v1/sessions/../etc/events")
        r = c.getresponse(); r.read()
        self.assertEqual(r.status, 404)


if __name__ == "__main__":
    unittest.main()
