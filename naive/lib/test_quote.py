import contextlib
import io
import json
import os
import tempfile
import unittest

import quote

PRICING = quote.load_pricing(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pricing", "pricing.json"))


def q(kind, **kw):
    urgency = kw.pop("urgency", None)
    segment = kw.pop("segment", None)
    tier = kw.pop("tier", None)
    return quote.compute(PRICING, kind, kw, urgency, segment, tier)


def run_cli(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        quote.main(list(args))
    return json.loads(buf.getvalue())


class QuoteTests(unittest.TestCase):
    def test_default_workloads(self):
        self.assertEqual(q("trace")["quote_usd"], 2000)       # floor, rush is optional now
        self.assertEqual(q("excel")["quote_usd"], 450)
        self.assertEqual(q("code")["quote_usd"], 450)
        self.assertEqual(q("patient")["quote_usd"], 7500)     # floor 5000 x 1.5 risk
        self.assertEqual(q("wells")["quote_usd"], 15000)
        self.assertEqual(q("checkup")["quote_usd"], 0)

    def test_rush_is_optional_and_adds_25_percent(self):
        self.assertEqual(q("trace", urgency="rush")["quote_usd"], 2500)

    def test_triage_and_small_business_tiers(self):
        self.assertEqual(q("trace", tier="triage")["quote_usd"], 750)
        self.assertEqual(q("trace", segment="small")["quote_usd"], 1200)
        self.assertEqual(q("trace", segment="small")["kind"], "trace_small")
        self.assertEqual(q("trace", tier="triage")["kind"], "trace_triage")

    def test_small_tier_uses_overridden_rates(self):
        r = q("trace", segment="small", docs=100, scanned_pages=10, requests=4, retries=2, lookups=10, review_hours=1)
        # V = 50+10+10+1 = 71 ; 3*71 + 1*100 + 4*40 = 473, below the 1200 floor
        self.assertEqual(r["internal"]["formula_amount"], 473.0)
        self.assertEqual(r["internal"]["k"], 3)
        self.assertEqual(r["quote_usd"], 1200)

    def test_triage_workload_limits(self):
        self.assertTrue(q("trace", tier="triage", docs=40)["fits_tier"])
        self.assertFalse(q("trace", tier="triage", docs=41)["fits_tier"])
        self.assertFalse(q("trace", tier="triage", scanned_pages=21)["fits_tier"])

    def test_aliases_resolve(self):
        self.assertEqual(q("other")["kind"], "trace")
        self.assertEqual(q("trace-back")["kind"], "trace")

    def test_large_job_beats_the_floor(self):
        r = q("trace", docs=2000, scanned_pages=800, requests=20, retries=5, lookups=100, review_hours=10)
        # V = 1000+800+25+10 = 1835; 4V = 7340; + 1500 + 800 = 9640 -> rounds up to 9650
        self.assertEqual(r["quote_usd"], 9650)
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
        self.assertIn("$2,000", body)
        self.assertIn("not-to-exceed", body)
        self.assertIn("reply to this email with the single word APPROVE", body)
        self.assertNotIn("variable", body.lower())
        self.assertNotIn(str(r["internal"]["variable_cost"]), body)

    def test_checkup_email_is_free(self):
        subject, body = quote.email_for(q("checkup"), "C-0009", "Team X")
        self.assertIn("no charge", body.lower())

    def test_two_option_email_for_a_small_business(self):
        out = run_cli("options", "--kind", "trace", "--segment", "small", "--docs", "35", "--scanned-pages", "5",
                      "--case", "C-0004", "--client", "Corner Cafe")
        prices = [o["quote_usd"] for o in out["options"]]
        self.assertEqual(prices, [750, 1200])
        body = out["email_body"]
        self.assertIn("Option A, Triage, $750", body)
        self.assertIn("Option B, Full investigation, $1,200", body)
        self.assertIn("APPROVE A or APPROVE B", body)
        self.assertIn("credited", body)
        self.assertEqual(out["credit_usd_if_upgrading"], 750)
        self.assertNotIn("variable", body.lower())

    def test_big_workload_skips_the_small_tiers(self):
        out = run_cli("options", "--kind", "trace", "--segment", "small", "--docs", "300", "--case", "C-0005")
        self.assertEqual(len(out["options"]), 1)
        self.assertEqual(out["options"][0]["kind"], "trace")

    def test_kinds_without_offers_get_a_single_quote(self):
        out = run_cli("options", "--kind", "excel", "--case", "C-0006")
        self.assertEqual(len(out["options"]), 1)
        self.assertEqual(out["options"][0]["quote_usd"], 450)

    def test_reply_classification(self):
        self.assertEqual(quote.classify_reply("APPROVE"), "approve")
        self.assertEqual(quote.classify_reply("Yes, go ahead.\n\nOn Sat, Nash wrote:\n> reply DECLINE to cancel"), "approve")
        self.assertEqual(quote.classify_reply("DECLINE"), "decline")
        self.assertEqual(quote.classify_reply("No thanks, we found the file"), "decline")
        self.assertEqual(quote.classify_reply("Not approved"), "decline")
        self.assertEqual(quote.classify_reply("approve but also cancel"), "unclear")
        self.assertEqual(quote.classify_reply("what does the report include?"), "unclear")
        self.assertEqual(quote.classify_reply("> APPROVE\n"), "unclear")

    def test_choice_reading(self):
        self.assertEqual(quote.classify_choice("APPROVE A"), "A")
        self.assertEqual(quote.classify_choice("approve option b please"), "B")
        self.assertEqual(quote.classify_choice("B"), "B")
        self.assertIsNone(quote.classify_choice("APPROVE"))
        self.assertIsNone(quote.classify_choice("approve a or b"))
        self.assertIsNone(quote.classify_choice("> APPROVE A\nwhat is the difference?"))

    def test_reply_cli_needs_a_letter_when_two_options(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "r.txt")
        with open(p, "w") as fh:
            fh.write("APPROVE")
        self.assertEqual(run_cli("reply", "--file", p, "--options", "2")["decision"], "unclear")
        self.assertEqual(run_cli("reply", "--file", p)["decision"], "approve")
        with open(p, "w") as fh:
            fh.write("APPROVE B")
        out = run_cli("reply", "--file", p, "--options", "2")
        self.assertEqual((out["decision"], out["choice"]), ("approve", "B"))

    def test_quoted_text_does_not_count_as_approval(self):
        reply = "Can you explain the minimum?\n\nOn Sat wrote:\n> Reply APPROVE to start"
        self.assertEqual(quote.classify_reply(reply), "unclear")

    def test_final_invoice_never_above_quote_and_flags_overrun(self):
        r = q("trace", docs=3000, scanned_pages=900, requests=20, retries=5, lookups=100, review_hours=10)
        fin = quote.final_invoice(PRICING, r, 2000)
        self.assertEqual(fin["invoice_usd"], 2000)
        self.assertTrue(fin["needs_person"])
        within = quote.final_invoice(PRICING, q("trace"), 2000)
        self.assertFalse(within["needs_person"])
        self.assertEqual(within["invoice_usd"], 2000)

    def test_cli_prints_json(self):
        out = run_cli("quote", "--kind", "trace", "--case", "C-0003", "--client", "Alderbank", "--docs", "120")
        self.assertEqual(out["quote_usd"], 2000)
        self.assertEqual(out["approval_word"], "APPROVE")
        rush = run_cli("quote", "--kind", "trace", "--docs", "120", "--rush")
        self.assertEqual(rush["quote_usd"], 2500)


if __name__ == "__main__":
    unittest.main()
