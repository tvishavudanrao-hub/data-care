import json
import os
import unittest

import quote

PRICING = quote.load_pricing(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pricing", "pricing.json"))


def q(kind, **kw):
    return quote.compute(PRICING, kind, kw)


class QuoteTests(unittest.TestCase):
    def test_default_workloads_match_the_posted_examples(self):
        self.assertEqual(q("trace")["quote_usd"], 2500)      # floor 2000 x 1.25 rush
        self.assertEqual(q("excel")["quote_usd"], 450)
        self.assertEqual(q("code")["quote_usd"], 450)
        self.assertEqual(q("patient")["quote_usd"], 7500)    # floor 5000 x 1.5 risk
        self.assertEqual(q("wells")["quote_usd"], 15000)
        self.assertEqual(q("checkup")["quote_usd"], 0)

    def test_aliases_resolve(self):
        self.assertEqual(q("other")["kind"], "trace")
        self.assertEqual(q("trace-back")["kind"], "trace")

    def test_large_job_beats_the_floor(self):
        r = q("trace", docs=2000, scanned_pages=800, requests=20, retries=5, lookups=100, review_hours=10)
        # V = 1000+800+25+10 = 1835; 4V = 7340; + 1500 + 800 = 9640; x1.25 = 12050
        self.assertEqual(r["quote_usd"], 12050)
        self.assertFalse(r["internal"]["floor_applied"])

    def test_missing_inputs_are_marked_assumed(self):
        r = q("trace", docs=50)
        self.assertEqual(r["inputs"]["docs"], 50)
        self.assertIn("scanned_pages", r["assumed_inputs"])
        self.assertNotIn("docs", r["assumed_inputs"])

    def test_quote_rounds_up_to_25(self):
        r = q("excel", docs=900, scanned_pages=0, retries=0, lookups=0, review_hours=0, requests=0)
        self.assertEqual(r["quote_usd"] % 25, 0)

    def test_email_asks_for_approval_and_hides_internal_costs(self):
        r = q("trace")
        subject, body = quote.email_for(r, "C-0003", "Alderbank")
        self.assertIn("APPROVE", subject)
        self.assertIn("$2,500", body)
        self.assertIn("not-to-exceed", body)
        self.assertIn("reply to this email with the single word APPROVE", body)
        self.assertNotIn("variable", body.lower())
        self.assertNotIn(str(r["internal"]["variable_cost"]), body)

    def test_checkup_email_is_free(self):
        subject, body = quote.email_for(q("checkup"), "C-0009", "Team X")
        self.assertIn("no charge", body.lower())

    def test_reply_classification(self):
        self.assertEqual(quote.classify_reply("APPROVE"), "approve")
        self.assertEqual(quote.classify_reply("Yes, go ahead.\n\nOn Sat, Nash wrote:\n> reply DECLINE to cancel"), "approve")
        self.assertEqual(quote.classify_reply("DECLINE"), "decline")
        self.assertEqual(quote.classify_reply("No thanks, we found the file"), "decline")
        self.assertEqual(quote.classify_reply("Not approved"), "decline")
        self.assertEqual(quote.classify_reply("approve but also cancel"), "unclear")
        self.assertEqual(quote.classify_reply("what does the report include?"), "unclear")
        self.assertEqual(quote.classify_reply("> APPROVE\n"), "unclear")

    def test_quoted_text_does_not_count_as_approval(self):
        reply = "Can you explain the minimum?\n\nOn Sat wrote:\n> Reply APPROVE to start"
        self.assertEqual(quote.classify_reply(reply), "unclear")

    def test_final_invoice_never_above_quote_and_flags_overrun(self):
        r = q("trace", docs=3000, scanned_pages=900, requests=20, retries=5, lookups=100, review_hours=10)
        fin = quote.final_invoice(PRICING, r, 2500)
        self.assertEqual(fin["invoice_usd"], 2500)
        self.assertTrue(fin["needs_person"])
        within = quote.final_invoice(PRICING, q("trace"), 2500)
        self.assertFalse(within["needs_person"])
        self.assertEqual(within["invoice_usd"], 2500)

    def test_cli_prints_json(self):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            quote.main(["quote", "--kind", "trace", "--case", "C-0003", "--client", "Alderbank", "--docs", "120"])
        out = json.loads(buf.getvalue())
        self.assertEqual(out["quote_usd"], 2500)
        self.assertEqual(out["approval_word"], "APPROVE")


if __name__ == "__main__":
    unittest.main()
