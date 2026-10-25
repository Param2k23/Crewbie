import json
import os
import tempfile
import unittest

from services.commitments import CommitmentError, CommitmentService, MemoryConsentGateway
from tests.commitments.helpers import ROSTER, SESSION, V1, V2, accept_all, fresh, msg


class ProtocolTests(unittest.TestCase):
    def test_fixture_states(self):
        with open("docs/implementation/fixtures/chat_transcript.json") as f:
            data = json.load(f)
        host, svc, *_ = fresh()
        for m in data["messages"]:
            res = host.handle_chat_message(msg(m["request_id"], m["member_ref"], m["text"]))
            self.assertEqual(res["state"], m["expected_state"], m["text"])
        self.assertTrue(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["confirmed"])

    def test_maybe_conditional_silence(self):
        host, svc, *_ = fresh()
        host.handle_chat_message(msg("1", "stu_maya", "maybe"))
        host.handle_chat_message(msg("2", "stu_taylor", "yes if it stays below my budget"))
        s = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
        self.assertEqual(s["members"], {"stu_alex": "pending", "stu_maya": "tentative",
                                        "stu_jordan": "pending", "stu_taylor": "conditional"})
        self.assertFalse(s["confirmed"])

    def test_three_of_four_stays_pending_then_confirms_once(self):
        host, svc, _, sink, *_ = fresh()
        accept_all(host, skip=("stu_jordan",))
        s = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
        self.assertEqual((s["proposal_state"], s["accepted_count"], s["error_code"]),
                         ("approval_pending", 3, "APPROVAL_INCOMPLETE"))
        self.assertEqual(sink.of_type("proposal_confirmed"), [])
        host.handle_chat_message(msg("j", "stu_jordan", "I accept version 2"))
        host.handle_chat_message(msg("j2", "stu_jordan", "I accept version 2"))  # repeat, new id
        self.assertEqual(len(sink.of_type("proposal_confirmed")), 1)

    def test_only_explicit_accepted_from_everyone_confirms(self):
        for last in ("yes if we leave later", "maybe", "sounds fun", "no", "I'm out"):
            host, svc, _, sink, *_ = fresh()
            host.handle_chat_message(msg("t", "stu_taylor", last))
            accept_all(host, skip=("stu_taylor",))  # the last accept triggers the confirmation check
            s = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
            self.assertFalse(s["confirmed"], last)
            self.assertEqual(sink.of_type("proposal_confirmed"), [], last)

    def test_stale_version_rejected(self):
        host, svc, *_ = fresh()
        r = host.handle_chat_message(msg("s", "stu_alex", "I accept version 1"))
        self.assertEqual((r["action"], r["error_code"]), ("stale", "PROPOSAL_STALE"))
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["accepted_count"], 0)

    def test_referenced_version_from_provider_reply(self):
        host, svc, *_ = fresh()
        r = host.handle_chat_message(msg("s", "stu_alex", "I accept", referenced_version=1))
        self.assertEqual(r["error_code"], "PROPOSAL_STALE")

    def test_duplicate_message_is_idempotent(self):
        host, svc, _, sink, *_ = fresh()
        host.handle_chat_message(msg("d", "stu_alex", "I accept version 2"))
        n = len(sink.events)
        r = host.handle_chat_message(msg("d", "stu_alex", "I accept version 2"))
        self.assertEqual(r["action"], "duplicate")
        self.assertEqual(len(sink.events), n)

    def test_revision_invalidates_approvals_no_auto_confirm(self):
        host, svc, _, sink, listener, *_ = fresh(V1)
        accept_all(host, version=1)  # confirms v1
        self.assertEqual(len(sink.of_type("proposal_confirmed")), 1)
        host.present_proposal(V2())
        old = svc.get_commitment_summary(SESSION, "plan_flagstaff_001", 1)
        new = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
        self.assertEqual(old["error_code"], "PROPOSAL_STALE")
        self.assertEqual(old["accepted_count"], 0)
        self.assertEqual((new["accepted_count"], new["confirmed"]), (0, False))
        self.assertTrue(listener.of_kind("approvals_invalidated"))
        self.assertEqual(len(sink.of_type("proposal_confirmed")), 1)  # still just the v1 one

    def test_invalidate_version_gateway_call(self):
        host, svc, *_ = fresh(V1)
        host.handle_chat_message(msg("1", "stu_alex", "I accept version 1"))
        svc.invalidate_version(SESSION, 1, 2)
        r = host.handle_chat_message(msg("2", "stu_maya", "I accept version 1"))
        self.assertIn(r["action"], ("ignored", "stale"))
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_001", 1)["accepted_count"], 0)

    def test_material_change_same_version_rejected(self):
        host, svc, *_ = fresh()
        changed = V2()
        changed["start_at"] = "2026-11-01T06:00:00-08:00"
        with self.assertRaises(CommitmentError) as cm:
            svc.register_proposal(changed)
        self.assertEqual(cm.exception.code, "VERSION_CONFLICT")

    def test_older_snapshot_cannot_replace_active(self):
        host, svc, *_ = fresh()
        with self.assertRaises(CommitmentError) as cm:
            svc.register_proposal(V1())
        self.assertEqual(cm.exception.code, "PROPOSAL_STALE")

    def test_out_of_order_messages_latest_sent_wins(self):
        host, svc, _, _, _, clock, _ = fresh()
        later = "2026-10-24T18:30:00+00:00"
        earlier = "2026-10-24T18:20:00+00:00"
        host.handle_chat_message(msg("o1", "stu_alex", "no", sent_at=later))
        r = host.handle_chat_message(msg("o2", "stu_alex", "I accept version 2", sent_at=earlier))
        self.assertEqual(r["action"], "ignored")
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["members"]["stu_alex"], "declined")

    def test_accept_typed_before_presentation_is_stale(self):
        host, svc, *_ = fresh()
        r = host.handle_chat_message(msg("e", "stu_alex", "I accept", sent_at="2026-10-24T17:00:00+00:00"))
        self.assertEqual(r["error_code"], "PROPOSAL_STALE")

    def test_withdrawal_blocks_confirmation(self):
        host, svc, _, sink, listener, *_ = fresh()
        accept_all(host, skip=("stu_taylor",))
        host.handle_chat_message(msg("w", "stu_taylor", "I'm out"))
        s = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
        self.assertEqual(s["proposal_state"], "blocked")
        self.assertTrue(listener.of_kind("member_withdrawn"))
        self.assertEqual(sink.of_type("proposal_confirmed"), [])

    def test_withdrawal_after_confirmation_revokes_and_does_not_reconfirm(self):
        host, svc, _, sink, listener, *_ = fresh()
        accept_all(host)
        host.handle_chat_message(msg("w", "stu_taylor", "I'm out"))
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["proposal_state"], "revoked")
        host.handle_chat_message(msg("back", "stu_taylor", "I accept version 2"))
        self.assertEqual(len(sink.of_type("proposal_confirmed")), 1)
        self.assertTrue(listener.of_kind("confirmation_revoked"))

    def test_consent_revocation_clears_acceptance(self):
        host, svc, _, sink, listener, _, consent = fresh()
        accept_all(host, skip=("stu_jordan",))
        host.handle_consent_revoked(SESSION, "stu_alex")
        s = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
        self.assertEqual(s["members"]["stu_alex"], "withdrawn")
        r = host.handle_chat_message(msg("j", "stu_jordan", "I accept version 2"))
        self.assertFalse(r["confirmed_now"])
        r = host.handle_chat_message(msg("a2", "stu_alex", "I accept version 2"))
        self.assertEqual(r["error_code"], "CONSENT_REQUIRED")
        self.assertEqual(sink.of_type("proposal_confirmed"), [])

    def test_missing_acceptance_consent_blocks(self):
        host, svc, _, sink, _, _, consent = fresh()
        consent.revoke("stu_maya", SESSION, "plan_acceptance")
        r = host.handle_chat_message(msg("m", "stu_maya", "I accept version 2"))
        self.assertEqual(r["error_code"], "CONSENT_REQUIRED")

    def test_unvalidated_proposal_never_confirms_or_posts(self):
        snap = V2()
        snap["validated"] = False
        host, svc, provider, sink, *_ = fresh(None)
        out = host.present_proposal(snap)
        self.assertEqual(out["action"], "awaiting_validation")
        self.assertEqual(provider.group_outbox, [])
        host.handle_chat_message(msg("a", "stu_alex", "I accept version 2"))  # not presented -> rejected
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["accepted_count"], 0)

    def test_untrusted_identity_ignored(self):
        host, svc, *_ = fresh()
        r = host.handle_chat_message({**msg("x", "stu_alex", "I accept version 2"), "identity_source": "client_claim"})
        self.assertEqual(r["error_code"], "IDENTITY_UNVERIFIED")
        self.assertEqual(svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["accepted_count"], 0)

    def test_non_participant_ignored(self):
        host, svc, *_ = fresh()
        r = host.handle_chat_message(msg("x", "stu_stranger", "I accept version 2"))
        self.assertEqual(r["action"], "ignored")

    def test_weak_positive_does_not_downgrade_acceptance_or_condition(self):
        host, svc, *_ = fresh()
        host.handle_chat_message(msg("1", "stu_alex", "I accept version 2"))
        host.handle_chat_message(msg("2", "stu_alex", "cool"))
        host.handle_chat_message(msg("3", "stu_taylor", "yes if we leave after 10"))
        host.handle_chat_message(msg("4", "stu_taylor", "sure"))
        m = svc.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)["members"]
        self.assertEqual((m["stu_alex"], m["stu_taylor"]), ("accepted", "conditional"))

    def test_structured_ui_approval(self):
        host, svc, *_ = fresh()
        res = svc.record_approval(SESSION, "plan_flagstaff_002", 2, "stu_alex",
                                  {"state": "accepted", "explicit": True}, request_id="btn1")
        self.assertEqual(res["record"]["state"], "accepted")
        self.assertTrue(res["record"]["explicit_acceptance"])

    def test_persistence_survives_restart_and_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "state.json")
            svc = CommitmentService(consent=_all_consent(), state_path=path)
            from apps.chat_bot.demo import build  # noqa: F401
            svc.register_proposal(V2())
            svc.mark_presented(SESSION, "plan_flagstaff_002", 2)
            svc.record_approval(SESSION, "plan_flagstaff_002", 2, "stu_alex", "I accept version 2", request_id="p1")
            svc2 = CommitmentService(consent=_all_consent(), state_path=path)
            s = svc2.get_commitment_summary(SESSION, "plan_flagstaff_002", 2)
            self.assertEqual(s["members"]["stu_alex"], "accepted")
            dup = svc2.record_approval(SESSION, "plan_flagstaff_002", 2, "stu_alex", "I accept version 2", request_id="p1")
            self.assertTrue(dup["duplicate"])


def _all_consent():
    c = MemoryConsentGateway()
    for r in ROSTER:
        c.grant(r, SESSION)
    return c


if __name__ == "__main__":
    unittest.main()
