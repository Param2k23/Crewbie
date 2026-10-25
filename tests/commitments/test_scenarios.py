import json
import unittest

from apps.chat_bot import scenarios
from apps.chat_bot.demo import ROSTER, SESSION, build, main
from apps.chat_bot.providers import MockMessagingProvider, ProviderUnavailable
from tests.commitments.helpers import msg


def wired():
    host, svc, provider, sink, listener, clock, consent = build()
    return host, svc, provider, sink, listener, clock, consent


def plan_and_present(host, text="Anyone free for dinner tomorrow?", who="stu_alex"):
    r = host.handle_chat_message(msg("req1", who, text))
    snap = host.negotiation.next_snapshot()
    host.present_proposal(snap)
    return r, snap


class ScenarioFlows(unittest.TestCase):
    def test_demo_scenarios_exit_zero(self):
        import contextlib, io
        for argv in (["--scenario", "weekend"], ["--scenario", "dinner"], ["--scenario", "newgroup"], []):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0, argv)

    def test_evening_meetup_four_participants_to_confirmation(self):
        host, svc, provider, sink, *_ = wired()
        r, snap = plan_and_present(host)
        self.assertEqual(r["action"], "planning_requested")
        self.assertEqual(snap["activity_type"], "meal")
        self.assertIn("Meal proposal", provider.group_outbox[-1]["text"])
        for i, who in enumerate(ROSTER):
            host.handle_chat_message(msg(f"c{i}", who, f"I accept version {snap['version']}"))
        self.assertEqual(len(sink.of_type("proposal_confirmed")), 1)
        self.assertIn("Confirmed: all 4", provider.group_outbox[-1]["text"])

    def test_two_day_weekend_trip_uses_same_engine(self):
        host, svc, provider, sink, *_ = wired()
        r, snap = plan_and_present(host, "We should go somewhere over fall break.", "stu_maya")
        self.assertEqual(snap["activity_type"], "trip")
        text = provider.group_outbox[-1]["text"]
        self.assertIn("Sat Oct 31", text)
        self.assertIn("Sun Nov 1", text)  # multi-day window rendered
        for i, who in enumerate(ROSTER):
            host.handle_chat_message(msg(f"c{i}", who, f"I accept version {snap['version']}"))
        self.assertTrue(svc.get_commitment_summary(SESSION, snap["plan_id"], snap["version"])["confirmed"])

    def test_request_to_planner_contains_no_raw_text(self):
        host, *_ = wired()
        host.handle_chat_message(msg("r", "stu_alex", "Anyone free for dinner tomorrow? I can only spend $30"))
        req = host.negotiation.requests[-1]
        self.assertNotIn("30", json.dumps(req))
        self.assertNotIn("text", req)
        self.assertEqual(req["activity_type"], "meal")

    def test_mixed_responses_never_confirm(self):
        host, svc, _, sink, *_ = wired()
        _, snap = plan_and_present(host)
        v = snap["version"]
        host.handle_chat_message(msg("1", "stu_alex", f"I accept version {v}"))
        host.handle_chat_message(msg("2", "stu_maya", "maybe"))
        host.handle_chat_message(msg("3", "stu_jordan", "yes if it's cheaper"))
        s = svc.get_commitment_summary(SESSION, snap["plan_id"], v)
        self.assertEqual(s["members"], {"stu_alex": "accepted", "stu_maya": "tentative",
                                        "stu_jordan": "conditional", "stu_taylor": "pending"})
        self.assertEqual(sink.of_type("proposal_confirmed"), [])

    def test_material_revision_resets_and_old_acceptance_rejected(self):
        host, svc, _, sink, listener, *_ = wired()
        _, snap = plan_and_present(host, "We should go somewhere over fall break.")
        for i, who in enumerate(ROSTER):
            host.handle_chat_message(msg(f"c{i}", who, f"I accept version {snap['version']}"))
        r = host.handle_chat_message(msg("chg", "stu_jordan", "Can we move this to Sunday?"))
        self.assertEqual(r["action"], "change_requested")
        self.assertEqual(svc.get_commitment_summary(SESSION, snap["plan_id"], snap["version"])["proposal_state"], "revoked")
        self.assertEqual(host.negotiation.requests[-1]["aspects"], ["date"])
        snap2 = host.negotiation.next_snapshot()
        host.present_proposal(snap2)
        self.assertNotEqual(snap["start_at"], snap2["start_at"])
        old = svc.get_commitment_summary(SESSION, snap["plan_id"], snap["version"])
        self.assertEqual((old["error_code"], old["accepted_count"]), ("PROPOSAL_STALE", 0))
        r = host.handle_chat_message(msg("old", "stu_alex", f"I accept version {snap['version']}"))
        self.assertEqual(r["error_code"], "PROPOSAL_STALE")
        self.assertEqual(svc.get_commitment_summary(SESSION, snap2["plan_id"], snap2["version"])["accepted_count"], 0)
        self.assertTrue(listener.of_kind("change_requested"))

    def test_cost_change_also_resets(self):
        host, svc, *_ = wired()
        _, snap = plan_and_present(host)
        host.handle_chat_message(msg("a", "stu_alex", f"I accept version {snap['version']}"))
        host.handle_chat_message(msg("chg", "stu_maya", "can we make it cheaper?"))
        snap2 = host.negotiation.next_snapshot()
        self.assertNotEqual(snap["cost_summary"], snap2["cost_summary"])
        host.present_proposal(snap2)
        self.assertEqual(svc.get_commitment_summary(SESSION, snap2["plan_id"], 2)["accepted_count"], 0)

    def test_participant_withdrawal_notifies_and_blocks(self):
        host, svc, provider, sink, listener, *_ = wired()
        _, snap = plan_and_present(host)
        for i, who in enumerate(ROSTER):
            if who != "stu_taylor":
                host.handle_chat_message(msg(f"c{i}", who, f"I accept version {snap['version']}"))
        r = host.handle_chat_message(msg("w", "stu_taylor", "sorry, I'm out"))
        self.assertEqual(r["state"], "withdrawn")
        self.assertEqual(r["proposal_state"], "blocked")
        self.assertEqual(listener.of_kind("member_withdrawn")[0]["member_ref"], "stu_taylor")
        self.assertEqual(sink.of_type("proposal_confirmed"), [])

    def test_cancellation_request_blocks_and_is_not_decided_by_chat(self):
        host, svc, _, sink, listener, *_ = wired()
        _, snap = plan_and_present(host)
        r = host.handle_chat_message(msg("c", "stu_maya", "let's cancel the dinner"))
        self.assertEqual(r["action"], "cancellation_requested")
        self.assertTrue(listener.of_kind("cancellation_requested"))
        self.assertEqual(svc.get_commitment_summary(SESSION, snap["plan_id"], snap["version"])["proposal_state"], "blocked")
        svc.cancel_proposal(SESSION)
        r = host.handle_chat_message(msg("a", "stu_alex", f"I accept version {snap['version']}"))
        self.assertEqual(r["action"], "ignored")

    def test_duplicate_planning_message_is_ignored(self):
        host, svc, provider, *_ = wired()
        host.handle_chat_message(msg("dup", "stu_alex", "Anyone free for dinner tomorrow?"))
        n = len(provider.group_outbox)
        r = host.handle_chat_message(msg("dup", "stu_alex", "Anyone free for dinner tomorrow?"))
        self.assertEqual(r["action"], "duplicate")
        self.assertEqual(len(provider.group_outbox), n)
        self.assertEqual(len(host.negotiation.requests), 1)

    def test_unrelated_new_plan_after_confirmation_is_a_new_request(self):
        host, svc, *_ = wired()
        _, snap = plan_and_present(host)
        for i, who in enumerate(ROSTER):
            host.handle_chat_message(msg(f"c{i}", who, f"I accept version {snap['version']}"))
        r = host.handle_chat_message(msg("n", "stu_maya", "Let's play badminton this weekend."))
        self.assertEqual(r["action"], "planning_requested")
        self.assertEqual(host.negotiation.requests[-1]["activity_type"], "game")


class OfflineTests(unittest.TestCase):
    def test_planner_offline_is_reported_not_faked(self):
        host, *_ = wired()
        host.negotiation.offline = True
        r = host.handle_chat_message(msg("r", "stu_alex", "Anyone free for dinner tomorrow?"))
        self.assertEqual((r["action"], r["error_code"]), ("planner_unavailable", "PROVIDER_UNAVAILABLE"))
        host.negotiation.offline = False
        r = host.handle_chat_message(msg("r2", "stu_alex", "Anyone free for dinner tomorrow?"))
        self.assertEqual(r["action"], "planning_requested")

    def test_no_planner_configured(self):
        host, *_ = wired()
        host.negotiation = None
        r = host.handle_chat_message(msg("r", "stu_alex", "Anyone free for dinner tomorrow?"))
        self.assertEqual(r["action"], "planner_unavailable")

    def test_provider_offline_state_still_correct_and_messages_flush_later(self):
        host, svc, provider, sink, *_ = wired()
        _, snap = plan_and_present(host)
        provider.fail_next = 1
        r = host.handle_chat_message(msg("a", "stu_alex", f"I accept version {snap['version']}"))
        self.assertEqual(r["state"], "accepted")  # state is the human's act, independent of delivery
        self.assertEqual(r["delivery"], "failed")
        self.assertEqual(len(host.undelivered), 1)
        self.assertEqual(host.flush_undelivered(), 0)
        self.assertIn("recorded your yes", provider.group_outbox[-1]["text"])

    def test_no_provider_at_all(self):
        host, svc, provider, sink, *_ = wired()
        host.provider = None
        out = host.present_proposal(_snap())
        self.assertEqual((out["action"], out["delivery"]), ("proposal_not_sent", "failed"))
        self.assertEqual(sink.of_type("approval_requested"), [])
        r = host.handle_chat_message(msg("a", "stu_alex", "I accept version 2"))
        self.assertEqual(r["error_code"], "PROPOSAL_NOT_PRESENTED")
        host.provider = provider  # provider comes back
        host.present_proposal(_snap())
        self.assertEqual(len(sink.of_type("approval_requested")), 1)


def _snap():
    from tests.commitments.helpers import V2
    return V2()


class GroupFormationTests(unittest.TestCase):
    SCOPE = "scope_match_1"

    def _form(self, host, consent, granted=("stu_alex", "stu_maya", "stu_jordan")):
        for ref in granted:
            consent.grant(ref, self.SCOPE, "introduction")
        return host.groups.form_group("g1", self.SCOPE, "badminton", "game", list(ROSTER),
                                      {"stu_alex": ["badminton", "chess"], "stu_maya": ["badminton"],
                                       "stu_jordan": ["Badminton", "baking"]}, session_id=SESSION)

    def test_non_consenting_member_never_contacted_or_named(self):
        host, svc, provider, _, _, _, consent = wired()
        out = self._form(host, consent)
        self.assertEqual(out["invited"], ["stu_alex", "stu_maya", "stu_jordan"])
        for i, who in enumerate(out["invited"]):
            host.groups.handle_private_message({"request_id": f"j{i}", "member_ref": who, "text": "join", "identity_source": "mock"})
        blob = json.dumps(provider.group_outbox + provider.private_outbox)
        self.assertNotIn("Taylor", blob)
        self.assertNotIn("stu_taylor", blob)
        self.assertNotIn("chess", blob)
        self.assertNotIn("baking", blob)
        self.assertIn("badminton", provider.group_outbox[0]["text"])

    def test_private_invites_reveal_no_other_names(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        self.assertEqual(len(provider.private_outbox), 3)
        for o in provider.private_outbox:
            for n in ("Alex", "Maya", "Jordan", "Taylor"):
                self.assertNotIn(n, o["text"])
        self.assertEqual(provider.group_outbox, [])  # nothing public until everyone answered

    def test_intro_waits_for_all_and_respects_decline(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        host.groups.handle_private_message({"request_id": "a", "member_ref": "stu_alex", "text": "join", "identity_source": "mock"})
        host.groups.handle_private_message({"request_id": "b", "member_ref": "stu_maya", "text": "no thanks", "identity_source": "mock"})
        self.assertEqual(provider.group_outbox, [])
        res = host.groups.handle_private_message({"request_id": "c", "member_ref": "stu_jordan", "text": "I'm in", "identity_source": "mock"})
        self.assertEqual(res["group"]["action"], "introduced")
        self.assertNotIn("Maya", provider.group_outbox[0]["text"])

    def test_without_consent_no_group_no_messages(self):
        host, svc, provider, _, _, _, consent = wired()
        out = host.groups.form_group("g2", "scope_none", "dinner", "meal", list(ROSTER), {})
        self.assertEqual((out["action"], out["error_code"]), ("blocked", "CONSENT_REQUIRED"))
        self.assertEqual((provider.group_outbox, provider.private_outbox), ([], []))
        one = self._form(host, consent, granted=("stu_alex",))
        self.assertEqual(one["action"], "blocked")  # a group of one is not a group

    def test_matched_for_one_activity_is_not_matched_for_another(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        other = host.groups.form_group("g3", "scope_other_activity", "a hike", "trip", list(ROSTER), {})
        self.assertEqual(other["error_code"], "CONSENT_REQUIRED")

    def test_consent_revoked_before_intro_drops_member(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        consent.revoke("stu_jordan", self.SCOPE, "introduction")
        for i, who in enumerate(["stu_alex", "stu_maya", "stu_jordan"]):
            host.groups.handle_private_message({"request_id": f"x{i}", "member_ref": who, "text": "join", "identity_source": "mock"})
        self.assertNotIn("Jordan", provider.group_outbox[0]["text"])

    def test_icebreaker_is_opt_in_and_activity_specific(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        for i, who in enumerate(["stu_alex", "stu_maya", "stu_jordan"]):
            host.groups.handle_private_message({"request_id": f"x{i}", "member_ref": who, "text": "join", "identity_source": "mock"})
        self.assertNotIn("Icebreaker (optional)", json.dumps(provider.group_outbox))  # only an offer so far
        r = host.handle_chat_message(msg("ib", "stu_maya", "icebreaker please"))
        self.assertEqual(r["action"], "icebreaker")
        self.assertIn("game or sport", provider.group_outbox[-1]["text"])
        self.assertNotIn("food", provider.group_outbox[-1]["text"].lower())

    def test_private_message_identity_must_be_trusted(self):
        host, svc, provider, _, _, _, consent = wired()
        self._form(host, consent)
        r = host.groups.handle_private_message({"request_id": "z", "member_ref": "stu_alex", "text": "join", "identity_source": "claimed"})
        self.assertEqual(r["error_code"], "IDENTITY_UNVERIFIED")


class NoFoodBiasTests(unittest.TestCase):
    def test_non_meal_plans_have_no_food_wording(self):
        host, svc, provider, *_ = wired()
        host.handle_chat_message(msg("r", "stu_alex", "Let's play badminton this weekend."))
        host.present_proposal(host.negotiation.next_snapshot())
        text = " ".join(o["text"] for o in provider.group_outbox).lower()
        for w in ("food", "pizza", "free meal"):
            self.assertNotIn(w, text)


if __name__ == "__main__":
    unittest.main()
