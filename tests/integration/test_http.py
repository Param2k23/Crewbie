import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

from services.api.main import make_handler
from services.api.runtime import Runtime, MEMBERS


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.runtime = Runtime()
        self.snap = self.runtime.seed("weekend")
        self.sid = self.snap["session_id"]
        self.stop = threading.Event()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.runtime, self.stop))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        conn.request(method, path, json.dumps(body) if body is not None else None,
                     {"Content-Type": "application/json", **(headers or {})})
        response = conn.getresponse()
        status, data = response.status, json.loads(response.read())
        conn.close()
        return status, data

    def test_health_and_public_snapshot(self):
        status, data = self.request("GET", f"/v1/sessions/{self.sid}/snapshot")
        self.assertEqual(status, 200)
        self.assertEqual(data["mode"], "DEMO/SYNTHETIC")
        for key in ("hard_budget_cap_cents", "blocked_windows", "counteroffer_hints", "estimated_cost_cents_by_ref"):
            self.assertNotIn(key, json.dumps(data))

    def test_real_http_approvals_drive_commitment_service(self):
        for i, ref in enumerate(MEMBERS):
            status, data = self.request("POST", f"/v1/sessions/{self.sid}/messages", {
                "member_ref": ref, "text": f"I accept version {self.snap['version']}",
                "request_id": f"msg_{i}", "synthetic_confirmed": True})
            self.assertEqual(status, 200)
        self.assertEqual(data["snapshot"]["state"], "confirmed")

    def test_judge_http_calls_revalidation_and_resets_approvals(self):
        status, data = self.request("POST", f"/v1/sessions/{self.sid}/constraint-changes", {
            "request_id": "judge_http", "synthetic_confirmed": True,
            "changed_constraint_ref": {"member_ref": MEMBERS[2], "kind": "hard_budget", "value": 2000}})
        self.assertEqual(status, 202)
        self.assertGreater(data["version"], self.snap["version"])

    def test_sse_transports_real_safe_events_and_resume(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=2)
        events = self.runtime.events.sink.events(self.sid)
        conn.request("GET", f"/v1/sessions/{self.sid}/events", headers={"Last-Event-ID": events[-2]["event_id"]})
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        lines = []
        while len(lines) < 8:
            line = response.fp.readline().decode()
            lines.append(line)
            if line.startswith("data:"):
                event = json.loads(line[5:])
                self.assertEqual(event["event_id"], events[-1]["event_id"])
                self.assertEqual(event["visibility"], "group_safe")
                break
        self.assertTrue(any(line.startswith("data:") for line in lines))
        response.close()
        conn.close()

    def test_no_private_profile_route(self):
        self.assertEqual(self.request("GET", "/v1/participants/stu_alex")[0], 404)

    def test_cross_origin_and_rebinding_rejected(self):
        self.assertEqual(self.request("GET", "/healthz", headers={"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.request("GET", "/healthz", headers={"Host": "attacker.example"})[0], 403)

    def test_bad_body_and_missing_synthetic_gate(self):
        self.assertEqual(self.request("POST", "/v1/demo/sessions", {"scenario": "evening"})[0], 400)
        self.assertEqual(self.request("POST", f"/v1/sessions/{self.sid}/messages", {
            "member_ref": MEMBERS[0], "text": "yes", "request_id": "x"})[0], 400)


if __name__ == "__main__":
    unittest.main()
