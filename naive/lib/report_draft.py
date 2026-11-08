#!/usr/bin/env python3
"""report_draft.py - Data Care client report draft (Python 3.8+, standard library only).

Turns the Reconstruction outputs (summary.json, rules.json, report_items.json, gaps.json, question.json)
into a plain-English report.md for the client. Validation adds its verdict before anything is sent.

    python3 report_draft.py --rebuilt-dir rebuilt/ --case C-0001 [--client "Alderbank Outfitters"]
                            [--workbook model.xlsx] --out rebuilt/report_draft.md
Code case (kind "code"): put rules.json, modification_log.json, backtest.json (and gaps.json, question.json if
any) in one folder; the code report is chosen automatically when backtest.json is there:
    python3 report_draft.py --rebuilt-dir records/ --case C-0002 --module invoicing.py --out report_draft.md

It only reads the JSON files the formula engine wrote. It never opens the client's workbook.
"""
import argparse
import json
import os
import re

LABEL_WORDS = {
    "recovered": "recovered as it was",
    "reconstructed and tested": "rebuilt and checked against your surviving numbers",
    "reconstructed but untested": "rebuilt, with nothing left to check it against",
    "unresolved": "left blank on purpose",
}
SECRET = re.compile(r"(?i)\b(password|passwd|secret|token|api[_-]?key)(\s*[=:]\s*)\S+")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def clean(text):
    """Plain text for the client: no secrets, no long dashes, one line."""
    text = SECRET.sub(r"\1\2[removed]", str(text or ""))
    text = text.replace("—", ", ").replace("–", "-")
    return re.sub(r"\s+", " ", text).strip()


def where(item):
    """'Model!B6:I6 (Discount rate, Q1 2025-Q4 2026)' -> 'Discount rate, Q1 2025-Q4 2026 (Model!B6:I6)'."""
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", item or "")
    return "%s (%s)" % (m.group(2), m.group(1)) if m else clean(item)


def plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def draft(rebuilt_dir, case, client=None, workbook=None):
    d = lambda name, default: load(os.path.join(rebuilt_dir, name), default)
    summary = d("summary.json", {})
    rules = d("rules.json", [])
    items = d("report_items.json", [])
    gaps = d("gaps.json", [])
    question = d("question.json", None)
    counts = summary.get("counts", {})
    tested = counts.get("reconstructed and tested", 0)
    untested = counts.get("reconstructed but untested", 0)
    recovered = counts.get("recovered", 0)
    unresolved = [i for i in items if i.get("label") == "unresolved"]
    open_gaps = [g for g in gaps if g.get("status", "open") in ("open", "requested")]

    L = ["# Data Care recovery report: %s" % clean(client or case), ""]
    L.append("Case %s%s. Drafted by the Reconstruction Agent; the Validation Agent checks the rebuilt model "
             "before this report is sent." % (case, (", workbook " + clean(workbook)) if workbook else ""))
    L += ["", "## In short", ""]
    L.append("- We rebuilt %s. %s reproduce every number that survived in your file when we recalculate them; "
             "%s no surviving number to check against." % (
                 plural(summary.get("formulas_rebuilt", tested + untested), "formula"),
                 plural(tested, "rebuilt cell"), plural(untested, "rebuilt cell") + (" has" if untested == 1 else " have")))
    L.append("- %s came back exactly from your file or your exports." % plural(recovered, "cell"))
    if unresolved or open_gaps:
        L.append("- %s need%s you (below). We left %s blank instead of guessing." % (
            plural(max(len(unresolved), len(open_gaps)), "item"),
            "s" if max(len(unresolved), len(open_gaps)) == 1 else "",
            "it" if max(len(unresolved), len(open_gaps)) == 1 else "them"))
    else:
        L.append("- Nothing is missing: every cell is accounted for.")
    if question:
        L.append("- We have one question for you (below).")

    if question or unresolved or open_gaps:
        L += ["", "## What we need from you", ""]
        if question:
            L.append("- **Question:** %s" % clean(question.get("question")))
            for k, opt in enumerate(question.get("options") or []):
                L.append("  - Option %d: %s" % (k + 1, clean(opt)))
        for g in open_gaps:
            what = clean(g.get("what"))
            m = re.match(r"^(.*?\))\s*:", what)          # keep "Label for Period (Cell)", drop the quoted reason
            head = m.group(1) if m else what.split(":")[0]
            L.append("- **%s**: we could not find this number in anything you sent, so we left it blank instead of "
                     "guessing. If you have it, send it and we will fill it in and recheck the model." % head)

    if rules:
        L += ["", "## How each line is worked out", ""]
        for r in rules:
            cells = r.get("cells") or []
            if isinstance(cells, str):
                cells = [cells]
            status = LABEL_WORDS.get(r.get("status"), clean(r.get("status")))
            L.append("- %s (%s): %s." % (clean(r.get("description")).rstrip("."), ", ".join(cells), status))

    rec = [i for i in items if i.get("label") == "recovered"]
    if rec:
        L += ["", "## Recovered as it was", ""]
        L += ["- %s" % where(i.get("item")) for i in rec]

    L += ["", "## What the labels mean", ""]
    L += ["- **%s**: %s." % (k, v) for k, v in (
        ("recovered", "survived intact, or copied exactly from your files"),
        ("reconstructed and tested", "rebuilt, and it reproduces every surviving number we could check it against"),
        ("reconstructed but untested", "rebuilt with nothing left to check it against; please look at these"),
        ("unresolved", "nothing reliable fits, so we left it blank rather than guess"))]
    L += ["", "## Validation", "", "Pending: the Validation Agent adds its result here before the report is sent.", ""]
    return "\n".join(L)


def draft_code(rebuilt_dir, case, client=None, module=None):
    """Report for a code case: rules.json, modification_log.json, backtest.json, gaps.json, question.json."""
    d = lambda name, default: load(os.path.join(rebuilt_dir, name), default)
    rules = d("rules.json", [])
    log = d("modification_log.json", [])
    bt = d("backtest.json", {})
    gaps = d("gaps.json", [])
    question = d("question.json", None)
    if isinstance(question, dict) and not question.get("question"):
        question = None
    module = module or os.path.basename(bt.get("script") or "") or "the module"
    checked, passed = bt.get("rows_checked", 0), bt.get("passed", 0)
    unreadable = bt.get("unreadable") or [{"row": n, "id": "row %s" % n, "reason": "unreadable"}
                                          for n in bt.get("unreadable_rows", [])]
    restored = [e for e in log if e.get("kind") == "restored"]
    rebuilt = [e for e in log if e.get("kind") in ("reconstructed", "inferred")]
    open_gaps = [g for g in gaps if g.get("status", "open") in ("open", "requested")]
    unresolved_rules = [r for r in rules if r.get("status") == "unresolved"]

    L = ["# Data Care recovery report: %s" % clean(client or case), ""]
    L.append("Case %s, module %s. Drafted by the Reconstruction Agent; the Validation Agent checks the rebuilt code "
             "before this report is sent." % (case, clean(module)))
    L += ["", "## In short", ""]
    if restored:
        L.append("- %s of %s came back exactly as it survived; we did not change %s." % (
            plural(len(restored), "part"), clean(module), "it" if len(restored) == 1 else "them"))
    L.append("- We rebuilt %s from your settings, your changelog and your past records." % plural(len(rebuilt), "missing piece"))
    if checked:
        L.append("- We tested the rebuilt code against %s: %s." % (
            plural(checked, "past invoice"),
            "every one matches to the cent" if passed == checked else "%d match to the cent, %d do not" % (passed, checked - passed)))
    if unreadable:
        L.append("- %s could not be read, so we left %s out of the test instead of guessing." % (
            plural(len(unreadable), "record"), "it" if len(unreadable) == 1 else "them"))
    L.append("- We have one question for you (below)." if question else "- We have no questions for you: your files settled every rule.")

    if question or unresolved_rules or open_gaps or unreadable:
        L += ["", "## What we need from you", ""]
        if question:
            L.append("- **Question:** %s" % clean(question.get("question")))
            for k, opt in enumerate(question.get("options") or []):
                L.append("  - Option %d: %s" % (k + 1, clean(opt)))
        for u in unreadable:
            L.append("- **%s** (row %s) is damaged in your export (%s). If you have a clean copy, send it and we "
                     "will add it to the test." % (clean(u.get("id")), u.get("row"), clean(u.get("reason"))))
        seen = {clean(u.get("id")) for u in unreadable}
        for g in open_gaps:
            if not any(x and x in clean(g.get("what")) for x in seen):
                L.append("- **%s**: %s" % (clean(g.get("gap_id")), clean(g.get("what"))))

    if restored:
        L += ["", "## Restored exactly", ""]
        L += ["- %s, lines %s: %s." % (clean(e.get("file")), clean(e.get("lines")),
                                       clean(e.get("note") or "kept exactly as it survived")) for e in restored]
    if rules:
        L += ["", "## Reconstructed", ""]
        for r in rules:
            mine = [e for e in rebuilt if e.get("rule_id") == r.get("rule_id")]
            files = sorted(set(clean(e.get("file")) for e in mine))
            where_ = "; ".join("%s lines %s" % (f, ", ".join(clean(e.get("lines")) for e in mine if clean(e.get("file")) == f))
                               for f in files)
            L.append("- %s%s: %s (%s)." % (clean(r.get("description")).rstrip("."), (" (" + where_ + ")") if where_ else "",
                                          LABEL_WORDS.get(r.get("status"), clean(r.get("status"))), r.get("rule_id")))
            if r.get("status") == "reconstructed and tested" and checked:
                L.append("  - Tested against %d past invoices; %d match to the cent." % (checked, passed))
            for alt in r.get("alternatives") or []:
                L.append("  - Other reading considered: %s" % clean(alt))
    if unreadable or unresolved_rules:
        L += ["", "## Left unresolved", ""]
        L += ["- %s (row %s): %s. We did not guess its values." % (clean(u.get("id")), u.get("row"), clean(u.get("reason")))
              for u in unreadable]
        L += ["- %s: %s." % (r.get("rule_id"), clean(r.get("description")).rstrip(".")) for r in unresolved_rules]

    L += ["", "## What the labels mean", ""]
    L += ["- **%s**: %s." % (k, v) for k, v in (
        ("recovered", "survived intact, or copied exactly from your files"),
        ("reconstructed and tested", "rebuilt, and it reproduces every surviving record we could check it against"),
        ("reconstructed but untested", "rebuilt with nothing left to check it against; please look at these"),
        ("unresolved", "nothing reliable fits, so we left it out rather than guess"))]
    L += ["", "## Validation", "", "Pending: the Validation Agent adds its result here before the report is sent.", ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Draft the client report from formula_infer.py or code-case outputs.")
    ap.add_argument("--rebuilt-dir", required=True)
    ap.add_argument("--case", required=True)
    ap.add_argument("--client")
    ap.add_argument("--workbook")
    ap.add_argument("--module", help="code case: the rebuilt file's name (e.g. invoicing.py)")
    ap.add_argument("--kind", choices=["excel", "code"], help="default: code when backtest.json is in --rebuilt-dir")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    kind = a.kind or ("code" if os.path.exists(os.path.join(a.rebuilt_dir, "backtest.json")) else "excel")
    if kind == "code":
        text = draft_code(a.rebuilt_dir, a.case, a.client, a.module)
    else:
        text = draft(a.rebuilt_dir, a.case, a.client, a.workbook)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("report draft: %s (%d lines)" % (a.out, text.count("\n") + 1))


if __name__ == "__main__":
    main()
