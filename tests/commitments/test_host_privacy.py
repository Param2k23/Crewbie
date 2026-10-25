import json
import unittest

from apps.chat_bot.providers import ProviderUnavailable, provider_from_env
from services.commitments import CommitmentError, check_outbound, PrivacyViolation
from tests.commitments.helpers import ROSTER, SESSION, V2, accept_all, fresh, msg

PRIVATE_CANARIES = ["hard_budget", "6000", "$60", "work shift", "blocked_window", "HARD_BUDGET", "chain of thought"]


class HostTests(unittest.TestCase):
    def test_snapshot_with_private_fields_rejected(self):
        host, svc, *_ = fresh(None)
        for key, val in [("hard_budget_cap_cents", 6000), ("internal_issue_codes", ["HARD_BUDGET"]),
                         ("estimated_cost_cents_by_ref", {"stu_alex": 5200}), ("blocked_windows", [])]:
            snap = V2()
            snap[key] = val
            with self.assertRaises(CommitmentError) as cm:
                svc.register_proposal(snap)
            self.assertEqual(cm.exception.code, "PRIVATE_FIELD_IN_SNAPSHOT", key)
        nested = V2()
        nested["extra"] = {"soft_preferences": {}}
        with self.assertRaises(CommitmentError):
            svc.register_proposal(nested)

    def test_per_person_estimate_requires_approval_flag(self):
        host, svc, *_ = fresh(None)
        snap = V2()
        snap["approved_per_person_estimate_cents"] = 5200
        with self.assertRaises(CommitmentError):
            svc.register_proposal(snap)

    def test_outbound_guard(self):
        for bad in ["my hard budget is low", "someone's budget cap is hit", "costs $61", "HARD_BUDGET exceeded"]:
            with self.assertRaises(PrivacyViolation):
                check_outbound(bad)
        check_outbound("costs $52", allowed_amounts=["52"])

    def test_no_group_message_leaks_private_data_over_full_flow(self):
        host, svc, provider, sink, *_ = fresh()
        host.handle_chat_message(msg("1", "stu_taylor", "yes if it stays below my $60 budget"))
        host.handle_chat_message(msg("2", "stu_jordan", "no, I can't miss my Saturday work shift"))
        host.handle_chat_message(msg("3", "stu_maya", "maybe"))
        host.follow_up()
        host.announce_no_solution(SESSION)
        host.present_proposal({**V2(), "version": 3, "plan_id": "plan_flagstaff_003"})
        blob = json.dumps(provider.group_outbox + sink.events)
        for secret in ["budget", "work shift", "Saturday", "$60", "6000", "reasoning"]:
            self.assertNotIn(secret, blob, secret)

    def test_condition_text_never_echoed_or_stored(self):
        host, svc, provider, sink, *_ = fresh()
        host.handle_chat_message(msg("1", "stu_taylor", "yes if we leave after 10 because of my shift"))
        self.assertNotIn("shift", json.dumps(provider.group_outbox + sink.events))
        self.assertNotIn("shift", json.dumps([r.evidence for r in svc._records.values()]))

    def test_provider_failure_never_reported_as_sent(self):
        host, svc, provider, *_ = fresh(None)
        provider.fail_next = 1
        out = host.present_proposal(V2())
        self.assertEqual(out["action"], "proposal_not_sent")
        self.assertEqual(out["error_code"], "PROVIDER_UNAVAILABLE")
        self.assertFalse(out["summary"]["presented"])
        r = host.handle_chat_message(msg("a", "stu_alex", "I accept version 2"))
        self.assertEqual(r["error_code"], "PROPOSAL_NOT_PRESENTED")
        host.present_proposal(V2())  # retry succeeds
        r = host.handle_chat_message(msg("b", "stu_alex", "I accept version 2"))
        self.assertEqual(r["state"], "accepted")

    def test_approval_requested_only_after_ack(self):
        host, svc, provider, sink, *_ = fresh(None)
        provider.fail_next = 1
        host.present_proposal(V2())
        self.assertEqual(sink.of_type("approval_requested"), [])
        host.present_proposal(V2())
        self.assertEqual(len(sink.of_type("approval_requested")), 1)

    def test_events_are_group_safe_and_whitelisted(self):
        host, svc, _, sink, *_ = fresh()
        accept_all(host)
        for e in sink.events:
            self.assertEqual(e["visibility"], "group_safe")
            self.assertIn(e["type"], {"approval_requested", "member_response_received", "proposal_confirmed"})
            self.assertTrue(e["synthetic"])

    def test_follow_up_is_rate_limited_and_skips_responders(self):
        host, svc, provider, _, _, clock, _ = fresh()
        self.assertEqual(host.follow_up()["action"], "none")  # too soon
        clock.advance(hours=7)
        host.handle_chat_message(msg("1", "stu_alex", "I accept version 2"))
        out = host.follow_up()
        self.assertNotIn("stu_alex", out["pending"])
        self.assertEqual(host.follow_up()["action"], "none")  # interval since last nudge
        clock.advance(hours=7)
        self.assertEqual(host.follow_up()["action"], "follow_up")
        clock.advance(hours=7)
        self.assertEqual(host.follow_up()["action"], "none")  # max nudges reached

    def test_clarification_asked_once_per_member(self):
        host, svc, provider, *_ = fresh()
        r1 = host.handle_chat_message(msg("1", "stu_maya", "sounds fun"))
        r2 = host.handle_chat_message(msg("2", "stu_maya", "cool"))
        self.assertIsNotNone(r1["reply"])
        self.assertIsNone(r2["reply"])


class IntroductionTests(unittest.TestCase):
    def test_no_introduction_or_icebreaker_without_consent(self):
        host, svc, provider, _, _, _, consent = fresh(None)
        out = host.introduce(SESSION, ["stu_alex", "stu_stranger"], SESSION, "lunch", {})
        self.assertEqual(out["error_code"], "CONSENT_REQUIRED")
        out = host.suggest_icebreaker(SESSION, ["stu_alex", "stu_stranger"], SESSION, "opportunity")
        self.assertEqual(out["error_code"], "CONSENT_REQUIRED")
        self.assertEqual(provider.group_outbox, [])

    def test_introduction_uses_only_shared_approved_interests(self):
        host, svc, provider, *_ = fresh(None)
        out = host.introduce(SESSION, ["stu_alex", "stu_maya"], SESSION, "the Flagstaff trip",
                             {"stu_alex": ["Hiking", "hackathons"], "stu_maya": ["hiking", "chess"]})
        self.assertEqual(out["shared_interests"], ["hiking"])
        text = provider.group_outbox[-1]["text"]
        self.assertIn("hiking", text)
        self.assertNotIn("chess", text)
        self.assertNotIn("hackathons", text)

    def test_private_exception_goes_only_to_member(self):
        host, svc, provider, *_ = fresh()
        host.request_private_exception("stu_jordan", SESSION, "plan_flagstaff_002", 2)
        self.assertEqual(len(provider.private_outbox), 1)
        self.assertEqual(provider.private_outbox[0]["target"], "stu_jordan")
        self.assertNotIn("Jordan", json.dumps(provider.group_outbox))


class ProviderTests(unittest.TestCase):
    def test_default_is_mock_and_discord_is_honestly_unavailable(self):
        self.assertEqual(provider_from_env({}).name, "mock")
        with self.assertRaises(ProviderUnavailable):
            provider_from_env({"CREWBIE_CHAT_PROVIDER": "discord", "DISCORD_BOT_TOKEN": "x"})

    def test_mock_resend_is_idempotent(self):
        p = provider_from_env({})
        a = p.send_group_message("c", "hi", request_id="r")
        b = p.send_group_message("c", "hi", request_id="r")
        self.assertEqual(a, b)
        self.assertEqual(len(p.group_outbox), 1)


if __name__ == "__main__":
    unittest.main()
