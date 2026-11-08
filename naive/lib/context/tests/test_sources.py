"""Tests for the sources a whole computer export brings: archives, big folders, mail exports, git history,
calendars and chat exports. Every fixture is built inline. Run: python3 -m pytest -q tests/"""
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from email.message import EmailMessage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "context_scan.py")
sys.path.insert(0, ROOT)

import context_scan as cs  # noqa: E402

RULE = "Orders over $5,000 get 10% off."
SECRET = "hunter" + "22pass"          # built by concatenation so secret scanners do not flag this file


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data.encode("utf-8") if isinstance(data, str) else data)


def run_cli(case, out, *extra):
    r = subprocess.run([sys.executable, SCRIPT, "--case-dir", case, "--case", "C-0300", "--out-dir", out] + list(extra),
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=case, timeout=300)
    assert r.returncode == 0, r.stderr.decode()
    return load(out) + (r.stdout.decode(),)


def run_inproc(case, out, **kw):
    s = cs.Scan(case, "C-0300", None, out, **kw)
    s.run()
    return load(out)


def load(out):
    j = lambda n: json.load(open(os.path.join(out, n), encoding="utf-8"))
    return j("evidence.json"), j("fragments.json"), j("gaps.json"), open(os.path.join(out, "inventory.md"), encoding="utf-8").read()


def blob(out):
    return "".join(open(os.path.join(out, n), encoding="utf-8").read()
                   for n in ("evidence.json", "fragments.json", "gaps.json", "inventory.md"))


def zip_bytes(members):
    """members: [(name, data)] or [(ZipInfo, data)]"""
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members:
            z.writestr(name, data)
    return b.getvalue()


def email_bytes(subject, body, attach=None, frm="cfo@client.example"):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, "ops@client.example", subject
    m["Date"] = "Tue, 14 Oct 2025 09:12:00 -0700"
    m.set_content(body)
    if attach:
        m.add_attachment(attach[1], maintype="text", subtype="csv", filename=attach[0])
    return bytes(m)


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ctx_src_")
        self.case = os.path.join(self.tmp, "case")
        self.out = os.path.join(self.tmp, "evidence")
        os.makedirs(self.case)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Archives(Tmp):
    def build(self):
        link = zipfile.ZipInfo("docs/link_to_passwd")
        link.external_attr = (0o120777 << 16)
        deep = zip_bytes([("deeper.zip", zip_bytes([("x.txt", "Late fee is 9% per month.\n")]))])
        inner = zip_bytes([("inner_rates.txt", "Commission is 3% of net revenue, capped at $2,500 per quarter.\n"),
                           ("deep.zip", deep)])
        data = zip_bytes([
            ("drive/notes/pricing_notes.txt", RULE + "\n"),
            ("drive/exports/board_report_q3.csv", "Metric,Amount\nNet revenue,45360\n"),
            ("drive/inner.zip", inner),
            ("/etc/evil.txt", "absolute path"),
            ("../escape.txt", "dot dot"),
            (link, "/etc/passwd"),
            ("drive/.ssh/id_rsa", "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n"),
            ("drive/.DS_Store", "junk"),
            ("drive/node_modules/x/index.js", "junk"),
            ("drive/bomb.txt", b"\x00" * (12 * 1024 * 1024)),
        ])
        write(os.path.join(self.case, "client_drive.zip"), data)
        tb = io.BytesIO()
        with tarfile.open(fileobj=tb, mode="w:gz") as t:
            body = b"Rush orders carry a surcharge of $50 on orders under $500.\n"
            ti = tarfile.TarInfo("old/policy.txt")
            ti.size = len(body)
            t.addfile(ti, io.BytesIO(body))
            sl = tarfile.TarInfo("old/link")
            sl.type, sl.linkname = tarfile.SYMTYPE, "/etc/shadow"
            t.addfile(sl)
        write(os.path.join(self.case, "old_files.tar.gz"), tb.getvalue())

    def test_members_scanned_and_unsafe_ones_reported(self):
        self.build()
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        srcs = [r["source"] for r in ev["rules"]]
        self.assertIn("client_drive.zip/drive/notes/pricing_notes.txt#line1", srcs)
        self.assertIn("client_drive.zip/drive/inner.zip/inner_rates.txt#line1", srcs)       # nested one level
        self.assertIn("old_files.tar.gz/old/policy.txt#line1", srcs)                       # tar.gz
        self.assertFalse([s for s in srcs if "deeper.zip" in s], "only one level of nesting is opened")
        self.assertIn("an archive nested more than one level deep, not opened", inv)
        self.assertTrue([x for x in ev["reported"] if x["source"].startswith("client_drive.zip/drive/exports/")])
        self.assertIn("absolute path", inv)
        self.assertIn("path with '..'", inv)
        self.assertIn("a link, not followed", inv)
        self.assertIn("possible key or credential file, never opened", inv)
        self.assertIn("archive bomb", inv)
        self.assertTrue([g for g in gaps if "client_drive.zip" in g["what"] and "not read" in g["what"]])
        self.assertNotIn("PRIVATE KEY", blob(self.out))
        self.assertFalse([f for f in fr if "DS_Store" in f["source_file"] or "node_modules" in f["source_file"]])
        for p in (os.path.join(self.tmp, "escape.txt"), os.path.join(self.case, "escape.txt"), "/etc/evil.txt"):
            self.assertFalse(os.path.exists(p), p)
        self.assertEqual(sorted(os.listdir(self.case)), ["client_drive.zip", "old_files.tar.gz"], "nothing unpacked")
        self.assertIn("## Sources", inv)
        self.assertRegex(inv, r"- archives \(\.zip, \.tar, \.tar\.gz\): 3")

    def test_size_and_count_limits(self):
        write(os.path.join(self.case, "a.zip"), zip_bytes([("n%d.txt" % i, RULE + "\n") for i in range(6)] +
                                                          [("big.txt", "x" * 5000 + "\n" + RULE)]))
        old = cs.MAX_ARCHIVE_MEMBERS, cs.MAX_ARCHIVE_BYTES
        cs.MAX_ARCHIVE_MEMBERS, cs.MAX_ARCHIVE_BYTES = 5, 120
        try:
            ev, fr, gaps, inv = run_inproc(self.case, self.out)
        finally:
            cs.MAX_ARCHIVE_MEMBERS, cs.MAX_ARCHIVE_BYTES = old
        self.assertIn("more than 5 members", inv)
        self.assertIn("read limit for one archive was reached", inv)
        self.assertTrue([g for g in gaps if g["what"].startswith("a.zip:")])
        self.assertTrue(ev["rules"], "members within the limits are still read")

    def test_broken_archive_is_a_gap(self):
        write(os.path.join(self.case, "broken.zip"), b"PK\x03\x04 not really a zip")
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        self.assertTrue([g for g in gaps if "broken.zip could not be opened as an archive" in g["what"]])


class BigFolder(Tmp):
    def build(self):
        write(os.path.join(self.case, "zephyr_pricing_notes.txt"), RULE + "\n")
        write(os.path.join(self.case, "Documents", "misc_17.txt"), "Zephyr pricing call.\nLate fees are 2% per month.\n")
        for i in range(12):
            write(os.path.join(self.case, "Documents", "personal", "trip_%02d.txt" % i),
                  "Packing list %d. Sunscreen is 20%% off this week.\n" % i)
        write(os.path.join(self.case, "Pictures", "img_001.heic"), b"\x00" * 64)
        write(os.path.join(self.case, "node_modules", "lib", "index.js"), "module.exports = {}\n")
        write(os.path.join(self.case, "__pycache__", "x.cpython-311.pyc"), b"\x00")
        write(os.path.join(self.case, ".DS_Store"), b"\x00")
        write(os.path.join(self.case, ".ssh", "id_ed25519"), "-----BEGIN OPENSSH PRIVATE KEY-----\n")
        write(os.path.join(self.case, ".cache", "blob.txt"), RULE)
        write(os.path.join(self.case, "server.pem"), "-----BEGIN PRIVATE KEY-----\n")
        mb = b""
        for subj, body in (("Zephyr pricing", "Volume rebate is 4% above 200 units."), ("Party", "Cake is 50% off.")):
            mb += b"From x@y Tue Oct 14 09:12:00 2025\n" + email_bytes(subj, body) + b"\n"
        write(os.path.join(self.case, "Mail", "all.mbox"), mb)

    def test_ranked_by_terms_rest_listed_by_name(self):
        self.build()
        ev, fr, gaps, inv, out = run_cli(self.case, self.out, "--max-files", "3", "--terms", "Zephyr pricing")
        files = {f["source_file"] for f in fr}
        self.assertIn("zephyr_pricing_notes.txt", files)          # term in the name
        self.assertIn("Documents/misc_17.txt", files)             # term in the content
        self.assertFalse([f for f in files if "trip_" in f], "unrelated personal files are not scanned")
        self.assertIn("## Seen, not scanned", inv)
        self.assertIn("- Documents/personal/trip_00.txt", inv)
        self.assertIn(".heic 1", inv)
        self.assertNotIn("Sunscreen", blob(self.out))
        self.assertIn("Mail/all.mbox/message-1.eml#line", " ".join(r["source"] for r in ev["rules"]))
        self.assertNotIn("Cake", blob(self.out), "in a big export a mailbox keeps only the matching messages")
        self.assertIn("seen, not scanned", out)
        self.assertIn("**.ssh**: key or credential folder, never opened", inv)
        self.assertIn("**server.pem**: possible key or credential file, never opened", inv)
        self.assertIn("**node_modules**: folder skipped", inv)
        self.assertIn("**.cache**: cache or system folder, skipped", inv)
        self.assertNotIn("**.DS_Store**", inv)
        self.assertIn("skipped, system files (.DS_Store and the like): 1", inv)
        self.assertNotIn("PRIVATE KEY", blob(self.out))

    def test_small_case_scans_everything(self):
        self.build()
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        self.assertTrue([f for f in fr if "trip_03" in f["source_file"]])
        self.assertNotIn("## Seen, not scanned", inv)

    def test_big_unknown_files_are_junk(self):
        write(os.path.join(self.case, "movie.mp4"), b"\x00" * 4096)
        write(os.path.join(self.case, "notes.txt"), RULE)
        old = cs.MAX_BINARY_BYTES
        cs.MAX_BINARY_BYTES = 1024
        try:
            ev, fr, gaps, inv = run_inproc(self.case, self.out)
        finally:
            cs.MAX_BINARY_BYTES = old
        self.assertNotIn("movie.mp4", inv)
        self.assertIn("skipped, large files of a type this tool does not read: 1", inv)


class MailExports(Tmp):
    def mbox(self, msgs):
        out = b""
        for m in msgs:
            out += b"From sender@client.example Tue Oct 14 09:12:00 2025\n" + m.replace(b"\r\n", b"\n") + b"\n"
        return out

    def test_mbox_eml_folder_and_emlx(self):
        m1 = email_bytes("Pricing rules", RULE + "\nThe portal password: " + SECRET + "\n",
                         attach=("board_report_q3.csv", b"Metric,Amount\nNet revenue,45360\n"))
        m2 = email_bytes("Lunch", "See you at noon.\n")
        write(os.path.join(self.case, "Takeout", "All mail.mbox"), self.mbox([m1, m2]))
        write(os.path.join(self.case, "mail", "a.eml"), email_bytes("Fees", "Late fees are 2% per month.\n"))
        raw = email_bytes("Tax", "Sales tax stays at 8% for all orders.\n")
        write(os.path.join(self.case, "Mail", "1.emlx"), b"%d\n" % len(raw) + raw + b"<?xml version=\"1.0\"?><plist/>")
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        srcs = [r["source"] for r in ev["rules"]]
        self.assertTrue([s for s in srcs if s.startswith("Takeout/All mail.mbox/message-1.eml#line")])
        self.assertTrue([s for s in srcs if s.startswith("mail/a.eml#")])
        self.assertTrue([s for s in srcs if s.startswith("Mail/1.emlx#")])
        self.assertTrue([f for f in fr if f["source_file"] == "Takeout/All mail.mbox/message-2.eml" and
                         f["location"] == "headers" and "Lunch" in f["notes"]])
        self.assertTrue([x for x in ev["reported"]
                         if x["source"].startswith("Takeout/All mail.mbox/message-1.eml/board_report_q3.csv")])
        self.assertNotIn(SECRET, blob(self.out))
        self.assertIn("- mailbox messages: 2", inv)

    def test_big_mailbox_keeps_relevant_messages_only(self):
        msgs = [email_bytes("Zephyr pricing", RULE)] + [email_bytes("Newsletter %d" % i, "Shoes are 30%% off, %d left." % i)
                                                       for i in range(4)]
        write(os.path.join(self.case, "inbox.mbox"), self.mbox(msgs))
        old = cs.MAX_MAIL_MESSAGES
        cs.MAX_MAIL_MESSAGES = 2
        try:
            ev, fr, gaps, inv = run_inproc(self.case, self.out, terms="Zephyr")
        finally:
            cs.MAX_MAIL_MESSAGES = old
        self.assertEqual({f["source_file"] for f in fr if f["location"] == "headers"}, {"inbox.mbox/message-1.eml"})
        self.assertIn("4 message(s) did not match the case terms", inv)
        self.assertNotIn("Shoes", blob(self.out))
        self.assertIn("- mailbox messages: 5 seen, 1 scanned", inv)


class CalendarAndChat(Tmp):
    def test_ics_events(self):
        write(os.path.join(self.case, "calendar.ics"), "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nDTSTART:20251014T090000Z\r\n"
              "SUMMARY:Dentist\r\nATTENDEE:mailto:someone@private.example\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\n"
              "DTSTART;VALUE=DATE:20251020\r\nSUMMARY:Pricing review\r\nDESCRIPTION:Agreed: late fee is 2% per month "
              "on balances\r\n  over $1\\,000.\\nNo other changes.\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        r = [x for x in ev["rules"] if x["source"] == "calendar.ics#event2"]
        self.assertTrue(r)
        self.assertIn(1000.0, r[0]["numbers"])
        self.assertTrue([f for f in fr if f["location"] == "event2" and f["type"] == "record"
                         and "2025-10-20" in f["notes"] and "Pricing review" in f["notes"]])
        self.assertFalse([f for f in fr if "Dentist" in f["notes"]], "events without evidence leave no record")
        self.assertNotIn("someone@private.example", blob(self.out))
        self.assertIn("- calendar events: 2", inv)

    def test_slack_export(self):
        d = os.path.join(self.case, "slack_export")
        write(os.path.join(d, "general", "2025-10-14.json"), json.dumps([
            {"type": "message", "user": "U012AB", "text": "<@U012AB> reminder: orders over $5,000 get 10% off",
             "ts": "1697270400.000100"},
            {"type": "message", "user": "U034CD", "text": "lunch?", "ts": "1697270500.000200"}]))
        write(os.path.join(d, "users.json"), json.dumps([{"id": "U012AB", "real_name": "Dana W", "profile": {
            "email": "dana@private.example", "phone": "+1 555 0100"}}]))
        write(os.path.join(d, "channels.json"), json.dumps([{"id": "C1", "name": "general"}]))
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        r = [x for x in ev["rules"] if x["source"] == "slack_export/general/2025-10-14.json#ts=1697270400.000100"]
        self.assertTrue(r)
        self.assertEqual(r[0]["numbers"], [5000.0, 0.1])
        self.assertIn("personal data, not scanned", inv)
        b = blob(self.out)
        self.assertNotIn("dana@private.example", b)
        self.assertNotIn("555 0100", b)
        self.assertIn("- chat messages: 2", inv)


GIT = shutil.which("git")


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="Ann Lee", GIT_AUTHOR_EMAIL="ann@private.example",
               GIT_COMMITTER_NAME="Ann Lee", GIT_COMMITTER_EMAIL="ann@private.example",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, HOME=repo)
    subprocess.run(["git", "-C", repo, "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"] + list(args),
                   check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


DISCOUNTS = "RATE = 0.1\n\n\ndef apply_discount(total):\n    if total > 5000:\n        return total * (1 - RATE)\n    return total\n"
BILLING_V1 = ("RATE = 0.02\n\n\n@audited\ndef apply_late_fee(balance):\n    if balance > 1000:\n        return balance * RATE\n"
              "    return 0\n\n\ndef bill(b):\n    return b + apply_late_fee(b)\n")
BILLING_V2 = "def bill(b):\n    return b + apply_late_fee(b)\n"
INVOICE = "from discounts import apply_discount\n\n\ndef invoice_total(lines):\n    return apply_discount(sum(lines))\n"


@unittest.skipUnless(GIT, "git is not installed")
class GitHistory(Tmp):
    def build_repo(self, repo):
        os.makedirs(repo)
        git(repo, "init", "-q")
        write(os.path.join(repo, "discounts.py"), DISCOUNTS)
        write(os.path.join(repo, "invoicing.py"), INVOICE)
        write(os.path.join(repo, "report.py"), "def report():\n    return 'ok'\n")
        write(os.path.join(repo, "pricing.py"), "def price(q):\n    return q * 12.5\n")
        write(os.path.join(repo, "billing.py"), BILLING_V1)
        write(os.path.join(repo, ".env"), "API_KEY=abc\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "Add discounts, invoicing, report, pricing and billing")
        git(repo, "rm", "-q", "discounts.py")
        write(os.path.join(repo, "billing.py"), BILLING_V2)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "Remove discounts module and the late fee (moved)")

    def test_repo_history_recovers_missing_code_safely(self):
        repo = os.path.join(self.case, "project")
        self.build_repo(repo)
        os.remove(os.path.join(repo, "report.py"))                                 # lost from the working copy
        write(os.path.join(repo, "pricing.py"), "def price(q:\n")                  # truncated, does not parse
        marker = os.path.join(self.tmp, "PWNED")
        with open(os.path.join(repo, ".git", "config"), "a") as fh:                # hostile client config and hook
            fh.write("[core]\n\tfsmonitor = touch %s\n\tpager = touch %s\n\thooksPath = .git/hooks\n" % (marker, marker))
        write(os.path.join(repo, ".git", "hooks", "post-checkout"), "#!/bin/sh\ntouch %s\n" % marker)
        os.chmod(os.path.join(repo, ".git", "hooks", "post-checkout"), 0o755)
        write(os.path.join(repo, ".git", "objects", "info", "alternates"), "/nonexistent/objects\n")
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        self.assertFalse(os.path.exists(marker), "client git config or hooks must never run")
        commits = [f for f in fr if f["location"] == "commit"]
        self.assertEqual(len(commits), 2)
        self.assertTrue(all(f["source_file"].startswith("git:") for f in commits))
        self.assertIn("Ann Lee", commits[0]["notes"])
        self.assertNotIn("ann@private.example", blob(self.out))
        first = [f["source_file"][4:44] for f in commits if "Add discounts" in f["notes"]][0]
        code = [f for f in fr if f["type"] == "code" and f["source_file"] == "git:%s:billing.py" % first]
        self.assertTrue(code, "the last version of a deleted function comes from the commit before its removal")
        self.assertIn("`apply_late_fee`", code[0]["notes"])
        self.assertIn("@audited\ndef apply_late_fee(balance):", code[0]["notes"])
        self.assertNotIn("def bill", code[0]["notes"])
        g = [x for x in gaps if "Function `apply_late_fee`" in x["what"]][0]
        self.assertTrue(g["where_to_look"][0].startswith("git history: `apply_late_fee` in billing.py at commit"))
        self.assertIn(code[0]["fragment_id"], g["where_to_look"][0])
        m = [x for x in gaps if "Module `discounts`" in x["what"]][0]
        self.assertTrue(m["where_to_look"][0].startswith("git history: discounts.py at commit"))
        self.assertTrue([f for f in fr if f["source_file"] == "git:%s:discounts.py" % first and
                         "def apply_discount(total):" in f["notes"]])
        self.assertTrue([f for f in fr if f["source_file"].endswith(":report.py") and "missing from the case" in f["notes"]])
        p = [x for x in gaps if "pricing.py does not parse" in x["what"]][0]
        self.assertTrue(p["where_to_look"][0].startswith("git history: committed version of pricing.py"))
        self.assertFalse([f for f in fr if f["source_file"].endswith(":.env")], "hidden files never come from history")
        self.assertIn("private copy of its objects and refs", inv)
        self.assertIn("- git commits: 2", inv)

    def test_bundle(self):
        repo = os.path.join(self.tmp, "src")
        self.build_repo(repo)
        git(repo, "bundle", "create", "-q", os.path.join(self.case, "backup.bundle"), "--all")
        write(os.path.join(self.case, "invoicing.py"), INVOICE)
        write(os.path.join(self.case, "billing.py"), BILLING_V2)
        ev, fr, gaps, inv, _ = run_cli(self.case, self.out)
        self.assertEqual(len([f for f in fr if f["location"] == "commit"]), 2)
        self.assertTrue([f for f in fr if f["type"] == "code" and f["source_file"].endswith(":discounts.py")])
        self.assertTrue([f for f in fr if f["type"] == "code" and f["source_file"].endswith(":billing.py")])
        self.assertIn("**backup.bundle**: git bundle, read from a private copy", inv)

    def test_git_missing_is_a_gap(self):
        self.build_repo(os.path.join(self.case, "project"))
        s = cs.Scan(self.case, "C-0300", None, self.out)
        s.git = None
        s.run()
        ev, fr, gaps, inv = load(self.out)
        self.assertTrue([g for g in gaps if "git is not installed here" in g["what"]])


if __name__ == "__main__":
    unittest.main()
