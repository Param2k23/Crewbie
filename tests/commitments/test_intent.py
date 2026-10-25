import unittest

from services.commitments.intent import classify_planning as c


class IntentTests(unittest.TestCase):
    def test_new_plans(self):
        cases = {
            "Anyone free for dinner tomorrow?": ("meal", "tomorrow"),
            "Let's play badminton this weekend.": ("game", "this weekend"),
            "We should go somewhere over fall break.": ("trip", "fall break"),
            "Let's do something this weekend": ("other", "this weekend"),
            "who's down for a movie tonight": ("event", "tonight"),
        }
        for text, (kind, tf) in cases.items():
            i = c(text, has_open_proposal=False)
            self.assertEqual((i.kind, i.activity_type, i.timeframe), ("new_plan", kind, tf), text)

    def test_approvals_and_chatter_are_not_plans(self):
        for text in ["I accept version 2", "maybe", "let's do it", "sounds fun", "no", "lol"]:
            self.assertEqual(c(text, has_open_proposal=False).kind, "none", text)

    def test_open_proposal_suppresses_new_plan(self):
        self.assertEqual(c("Let's go Saturday for dinner, anyone?", has_open_proposal=True).kind, "none")

    def test_change_and_cancel(self):
        i = c("Can we move this plan to Saturday?", has_open_proposal=True)
        self.assertEqual((i.kind, i.timeframe, "date" in i.aspects), ("change_request", "saturday", True))
        self.assertIn("cost", c("can we make it cheaper?", has_open_proposal=True).aspects)
        self.assertEqual(c("let's cancel the trip", has_open_proposal=True).kind, "cancel_request")
        self.assertEqual(c("I need to cancel", has_open_proposal=True).kind, "none")  # personal => reply parser

    def test_no_raw_text_in_intent(self):
        i = c("can we move it to Saturday? my budget is $40", has_open_proposal=True)
        self.assertNotIn("40", repr(i))
