import unittest

from services.commitments import classify_reply as c


class ParserTests(unittest.TestCase):
    def test_required_mappings(self):
        cases = {
            "maybe": "tentative", "Maybe!": "tentative", "sounds fun": "interested",
            "Sounds interesting": "interested", "yes if it stays below my budget": "conditional",
            "Yes, if we leave after 10": "conditional", "no": "declined", "I decline": "declined",
            "I'm out": "withdrawn", "count me out": "withdrawn", "not sure yet": "tentative",
            "I accept this Sunday trip plan": "accepted", "I confirm plan version 2": "accepted",
            "I accept but only if it's cheaper": "conditional", "I accept, but": "conditional",
            "I can't confirm yet": "tentative", "I don't accept": "declined", "I guess": "tentative",
        }
        for text, want in cases.items():
            self.assertEqual(c(text).state, want, text)

    def test_ambiguous_never_accepts(self):
        for text in ["sure", "ok", "yes", "sounds good", "I'm in", "cool", "nice", "down", "yep", "probably yes",
                     "I accept?", "do I accept?", "lol", "", "   "]:
            r = c(text)
            self.assertNotEqual(r.state, "accepted", text)
            self.assertFalse(r.explicit, text)

    def test_plain_yes_only_counts_when_reply_scoped(self):
        self.assertEqual(c("yes", reply_scoped=True).state, "accepted")
        self.assertEqual(c("yes if we leave later", reply_scoped=True).state, "conditional")
        self.assertEqual(c("sure", reply_scoped=True).state, "interested")
        self.assertEqual(c("maybe", reply_scoped=True).state, "tentative")

    def test_version_reference_extracted(self):
        self.assertEqual(c("I accept version 3").referenced_version, 3)
        self.assertEqual(c("approve v2").referenced_version, 2)
        self.assertEqual(c("confirm plan_flagstaff_001").referenced_plan_id, "plan_flagstaff_001")
