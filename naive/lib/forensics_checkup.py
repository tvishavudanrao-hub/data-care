#!/usr/bin/env python3
"""forensics_checkup.py: clinic checkup and cc.py output on top of forensics_scan.py. Static and read-only.

    python3 forensics_checkup.py --case C-0002 --in-dir ./repo --out-dir ./out --team "Team X" --repo-url https://... [--osv-response osv.json]

Does everything forensics_scan.py does (recursively), plus:
  deps.json / osv_query.json   dependencies found in requirements.txt and package.json, and the body to POST to
                               https://api.osv.dev/v1/querybatch (the agent sends it with web_fetch; this script has no network)
  checkup.json, checkup_report.md   high / medium / low counts and a plain-English report (never contains a secret value)
  cc_commands.txt              the cc.py commands that log each fragment, gap and the checkup row
Standard library only, Python 3.8+.
"""
import argparse
import json
import os
import re
import shlex

import forensics_scan as fs

HIGH_WORDS = ("private key", "live api key", "aws access key", "known vulnerabilit")


def read_deps(root):
    deps = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "node_modules")]
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            try:
                if f == "requirements.txt":
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        for line in fh:
                            m = re.match(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*([\w.\-]+)", line)
                            if m:
                                deps.append({"ecosystem": "PyPI", "name": m.group(1), "version": m.group(2), "file": rel})
                elif f == "package.json":
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        pkg = json.load(fh)
                    for sect in ("dependencies", "devDependencies"):
                        for name, ver in (pkg.get(sect) or {}).items():
                            v = str(ver).lstrip("^~=v ")
                            if re.match(r"^\d+(\.\d+)*$", v):
                                deps.append({"ecosystem": "npm", "name": name, "version": v, "file": rel})
            except (ValueError, OSError):
                continue
    return deps


def osv_query(deps):
    return {"queries": [{"package": {"name": d["name"], "ecosystem": d["ecosystem"]}, "version": d["version"]} for d in deps]}


def apply_osv(deps, response):
    out = []
    for d, res in zip(deps, response.get("results", [])):
        ids = [v.get("id", "?") for v in (res or {}).get("vulns", [])]
        if ids:
            out.append(fs.finding("undocumented", "%s (%s)" % (d["file"], d["name"]),
                                  "known vulnerabilities in %s %s: %s" % (d["name"], d["version"], ", ".join(ids[:5])), "n/a", 0.9))
    return out


def severity(f):
    d = f["detail"].lower()
    if any(k in d for k in HIGH_WORDS):
        return "high"
    if f["class"] in ("missing", "corrupted") or "password" in d or "eicar" in d:
        return "medium"
    return "low"


def checkup(dr, extra, case, team):
    items = [(r["file"], f) for r in dr["files"] for f in r["findings"]] + [(f["where"], f) for f in extra]
    counts = {"high": 0, "medium": 0, "low": 0}
    for _, f in items:
        counts[severity(f)] += 1
    lines = ["# Checkup report for %s" % (team or case), "",
             "Files scanned: %d. High: %d, medium: %d, low: %d." % (len(dr["files"]), counts["high"], counts["medium"], counts["low"]), ""]
    for level in ("high", "medium", "low"):
        sel = [(w, f) for w, f in items if severity(f) == level]
        if sel:
            lines.append("## %s priority" % level.capitalize())
            lines += ["- %s, %s: %s" % (w, f["where"], f["detail"]) for w, f in sel]
            lines.append("")
    lines.append("We only read your files; nothing was run. Secret values are never copied into this report.")
    return counts, "\n".join(lines) + "\n"


def cc_lines(case, frags, gaps, counts, team, repo_url):
    out = []
    for f in frags:
        out.append("python3 cc.py fragment --id %s --case %s --source-file %s --location %s --type %s --confidence %s --notes %s --by forensics" %
                   (f["fragment_id"], case, shlex.quote(f["source_file"]), shlex.quote(str(f.get("location") or "")),
                    f["type"], f.get("confidence", 0.5), shlex.quote(f.get("notes") or "")))
    for g in gaps:
        out.append("python3 cc.py gap --id %s --case %s --what %s --why %s --where-to-look %s" %
                   (g["gap_id"], case, shlex.quote(g["what"]), shlex.quote(g.get("why") or ""),
                    " ".join(shlex.quote(w) for w in g["where_to_look"])))
    out.append("python3 cc.py checkup --case %s --team %s --repo-url %s --high %d --medium %d --low %d" %
               (case, shlex.quote(team or ""), shlex.quote(repo_url or ""), counts["high"], counts["medium"], counts["low"]))
    return out


def run(case, in_dir, out_dir, team="", repo_url="", osv_response=None):
    dr = fs.scan(case, in_dir, out_dir)
    deps = read_deps(in_dir)
    extra = apply_osv(deps, osv_response) if osv_response else []
    counts, report = checkup(dr, extra, case, team)
    with open(os.path.join(out_dir, "forensics_fragments.json")) as fh:
        frags = json.load(fh)
    with open(os.path.join(out_dir, "forensics_gaps.json")) as fh:
        gaps = json.load(fh)
    num = case.split("-")[-1]
    for f in extra:
        frags.append({"fragment_id": "F-%s-%03d" % (num, fs.FRAG_BASE + len(frags) + 1), "source_file": f["where"], "location": f["where"],
                      "type": "clue", "confidence": f["confidence"], "notes": "%s: %s" % (f["class"], f["detail"])})
    outputs = {"deps.json": deps, "osv_query.json": osv_query(deps), "forensics_fragments.json": frags,
               "checkup.json": dict(counts, case_id=case, team=team, repo_url=repo_url)}
    for fn, obj in outputs.items():
        with open(os.path.join(out_dir, fn), "w") as fh:
            json.dump(obj, fh, indent=2)
    with open(os.path.join(out_dir, "checkup_report.md"), "w") as fh:
        fh.write(report)
    with open(os.path.join(out_dir, "cc_commands.txt"), "w") as fh:
        fh.write("\n".join(cc_lines(case, frags, gaps, counts, team, repo_url)) + "\n")
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--team", default="")
    ap.add_argument("--repo-url", default="")
    ap.add_argument("--osv-response")
    a = ap.parse_args()
    resp = None
    if a.osv_response:
        with open(a.osv_response) as fh:
            resp = json.load(fh)
    print(json.dumps(run(a.case, a.in_dir, a.out_dir, a.team, a.repo_url, resp)))
