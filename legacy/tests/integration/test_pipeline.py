import json
import unittest
from copy import deepcopy

from services.api.runtime import Runtime, MEMBERS, BoundaryError
from services.participants.service import PrivacyError
from services.realtime.schema import EventRejected
from apps.chat_bot.providers import MockMessagingProvider
from apps.chat_bot.discord_live import validate_members


class PipelineTests(unittest.TestCase):
    def seed(self, kind="evening", provider=None):
        r = Runtime(provider)
        s = r.seed(kind, matching=True, sharing=True, introduction=True)
        return r, s["session_id"], s

    def approve(self, r, sid, s):
        for i, ref in enumerate(MEMBERS):
            r.message(sid, ref, f"I accept version {s['version']}", f"accept_{s['version']}_{i}", version=s["version"])

    def change(self, ref=MEMBERS[2], value=2000, kind="hard_budget", rid="change"):
        return {"request_id": rid, "synthetic_confirmed": True,
                "changed_constraint_ref": {"member_ref": ref, "kind": kind, "value": value}}

    def test_A_consented_skill_handoff_to_real_modules(self):
        r, sid, s = self.seed("unlocks")
        self.assertTrue(r.sessions[sid]["opportunity"]["source_url"])
        self.assertTrue(r.sessions[sid]["opportunity"]["synthetic"])
        self.assertEqual({ref for _, ref, _ in r.evaluator.calls}, set(MEMBERS))
        self.assertIn("match_requested", [e["type"] for e in r.events.sink.events(sid)])
        self.approve(r, sid, s)
        self.assertEqual(r.snapshot(sid)["state"], "confirmed")
        self.assertFalse(r.snapshot(sid)["booking_confirmed"])

    def test_A_requires_each_separate_consent(self):
        for flag in ("matching", "sharing", "introduction"):
            args = dict(matching=True, sharing=True, introduction=True)
            args[flag] = False
            with self.assertRaises(BoundaryError):
                Runtime().seed("unlocks", **args)

    def test_B_rejected_then_agent_counteroffer_and_approvals(self):
        r, sid, s = self.seed()
        types = [e["type"] for e in r.events.sink.events(sid)]
        self.assertIn("proposal_rejected", types)
        self.assertIn("counteroffer_proposed", types)
        r.message(sid, MEMBERS[0], "maybe", "maybe")
        r.message(sid, MEMBERS[1], "yes if it is cheap", "conditional")
        self.assertFalse(r.snapshot(sid)["commitments"]["confirmed"])
        self.approve(r, sid, s)
        self.assertEqual(r.snapshot(sid)["state"], "confirmed")
        self.assertEqual([e["type"] for e in r.events.sink.events(sid)].count("proposal_confirmed"), 1)

    def test_C_two_day_plan_and_actual_replan(self):
        r, sid, s = self.seed("weekend")
        from services.negotiation.models import parse_ts
        self.assertGreaterEqual((parse_ts(s["plan"]["end_at"]) - parse_ts(s["plan"]["start_at"])).total_seconds(), 24*3600)
        self.approve(r, sid, s)
        changed = r.change(sid, self.change())
        self.assertNotEqual(changed["state"], "confirmed")
        self.assertGreater(changed["version"], s["version"])
        self.assertEqual(changed["commitments"]["accepted_count"], 0)
        self.assertIn("proposal_revised", [e["type"] for e in r.events.sink.events(sid)])
        self.assertTrue(any(e["payload"].get("request_id") == "change" for e in r.events.sink.events(sid)))

    def test_stale_approval_after_change(self):
        r, sid, s = self.seed("weekend")
        r.change(sid, self.change())
        result = r.message(sid, MEMBERS[0], f"I accept version {s['version']}", "stale", version=s["version"])
        self.assertEqual(result["action"]["error_code"], "PROPOSAL_STALE")
        self.assertEqual(result["snapshot"]["commitments"]["accepted_count"], 0)

    def test_duplicate_chat_does_not_double_emit(self):
        r, sid, s = self.seed()
        r.message(sid, MEMBERS[0], f"I accept version {s['version']}", "duplicate")
        n = len(r.events.sink.events(sid))
        r.message(sid, MEMBERS[0], f"I accept version {s['version']}", "duplicate")
        self.assertEqual(len(r.events.sink.events(sid)), n)

    def test_duplicate_changes_and_changed_payload_rejected(self):
        r, sid, _ = self.seed("weekend")
        first = r.change(sid, self.change())
        self.assertEqual(first, r.change(sid, self.change()))
        with self.assertRaises(BoundaryError):
            r.change(sid, self.change(value=3000))

    def test_provider_failure_never_opens_approvals(self):
        p = MockMessagingProvider(fail_next=1)
        r, sid, s = self.seed(provider=p)
        self.assertFalse(s["commitments"]["presented"])
        self.approve(r, sid, s)
        self.assertFalse(r.snapshot(sid)["commitments"]["confirmed"])
        self.assertNotIn("approval_requested", [e["type"] for e in r.events.sink.events(sid)])
        r.present(sid)
        self.approve(r, sid, s)  # fresh request IDs are needed after failed approvals
        self.assertTrue(r.snapshot(sid)["commitments"]["presented"])

    def test_revoke_stops_evaluation_matching_sharing_and_confirmation(self):
        r, sid, s = self.seed("unlocks")
        self.approve(r, sid, s)
        out = r.change(sid, self.change(MEMBERS[0], "withdraw", "withdraw"))
        self.assertNotEqual(out["state"], "confirmed")
        self.assertFalse(r.consent.has_consent(MEMBERS[0], sid, "matching"))
        with self.assertRaises(PrivacyError):
            r.participants.owner(MEMBERS[0]).find_mutual_candidates(sid, r.sessions[sid]["opportunity"]["opportunity_id"], 4)
        with self.assertRaises(BoundaryError):
            r.seed("unlocks", matching=True, sharing=True, introduction=True)

    def test_events_and_chat_have_no_private_fields_or_values(self):
        r, sid, s = self.seed("weekend")
        self.approve(r, sid, s)
        r.change(sid, self.change())
        public = json.dumps([r.events.sink.events(sid), r.provider.group_outbox])
        for forbidden in ("hard_budget_cap_cents", "blocked_windows", "counteroffer_hints", "soft_penalty", "HARD_BUDGET", "estimated_cost_cents_by_ref"):
            self.assertNotIn(forbidden, public)
        self.assertEqual(r.events.sink.rejected, [])
        self.assertEqual(r.coordinator.sink_errors, 0)

    def test_private_event_rejected(self):
        r, sid, _ = self.seed()
        event = deepcopy(r.events.sink.events(sid)[0])
        event.update(event_id="evil", visibility="internal")
        with self.assertRaises(EventRejected):
            r.events.emit(event)

    def test_duplicate_events_are_idempotent(self):
        r, sid, _ = self.seed()
        event = r.events.sink.events(sid)[0]
        r.events.sink.emit(event)
        self.assertEqual(len({e["event_id"] for e in r.events.sink.events(sid)}), len(r.events.sink.events(sid)))

    def test_hard_constraint_never_silently_waived(self):
        r, sid, _ = self.seed("weekend")
        s = r.change(sid, self.change(value=0))
        self.assertEqual(s["state"], "failed")
        self.assertEqual(s["error_code"], "NO_FEASIBLE_PLAN")

    def test_judge_requires_server_side_synthetic_gate(self):
        r, sid, _ = self.seed()
        req = self.change()
        req["synthetic_confirmed"] = False
        with self.assertRaises(BoundaryError):
            r.change(sid, req)
        r.sessions[sid]["synthetic"] = False
        with self.assertRaises(BoundaryError):
            r.change(sid, self.change())

    def test_client_identity_flag_is_not_live_identity(self):
        r, sid, s = self.seed()
        out = r.message(sid, MEMBERS[0], f"I accept version {s['version']}", "spoof", identity_source="client")
        self.assertEqual(out["action"]["error_code"], "IDENTITY_UNVERIFIED")

    def test_discord_mapping_requires_four_unique_authorized_testers(self):
        with self.assertRaises(ValueError):
            validate_members('{}')
        self.assertEqual(set(validate_members(json.dumps({str(i): ref for i, ref in enumerate(MEMBERS)})).values()), set(MEMBERS))

    def test_decline_vetoes_proposal_without_revoking_activity_consent(self):
        r, sid, s = self.seed()
        out = r.message(sid, MEMBERS[0], "no", "decline")
        self.assertNotEqual(out["snapshot"]["state"], "confirmed")
        self.assertTrue(r.consent.has_consent(MEMBERS[0], sid, "plan_acceptance"))

    def test_cancellation_is_coordinated_and_clears_confirmation(self):
        r, sid, s = self.seed("weekend")
        self.approve(r, sid, s)
        out = r.message(sid, MEMBERS[0], "Let's cancel the trip", "cancel")
        self.assertEqual(out["snapshot"]["state"], "cancelled")
        self.assertFalse(out["snapshot"]["booking_confirmed"])

    def test_minimized_evaluator_cannot_accept_other_members_cost(self):
        r, sid, s = self.seed()
        plan = deepcopy(r.coordinator._get(sid).current_plan)
        plan["estimated_cost_cents_by_ref"] = {MEMBERS[1]: 100}
        with self.assertRaises(PrivacyError):
            r.participants.evaluator(sid, minimized_costs=True).evaluate_plan_private(MEMBERS[0], plan)


if __name__ == "__main__":
    unittest.main()
