#!/usr/bin/env python3
"""forensics_scan.py: static, read-only first look at a case's files. Never runs or opens client files as code.

    python3 forensics_scan.py --case C-0001 --in-dir ./incoming --out-dir ./out

Writes to --out-dir: damage_report.json, fragments.json, gaps.json, working/ (clean copies) and quarantine/
(flagged files, original bytes untouched). Standard library only, Python 3.8+.
Never prints or stores a secret value: only file, line and kind.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET

# Harmless antivirus test marker, split so this source file is not itself flagged.
EICAR_MARK = b"EICAR-STANDARD-" + b"ANTIVIRUS-TEST-FILE"
SECRETS = [("aws access key", re.compile(rb"AKIA[0-9A-Z]{16}")),
           ("live api key", re.compile(rb"sk_live_[0-9A-Za-z]{8,}")),
           ("private key block", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
           ("password assignment", re.compile(rb"(?i)password\s*[=:]\s*\S{4,}"))]
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sniff(data):
    if data[:4] == b"PK\x03\x04":
        try:
            names = zipfile.ZipFile(io.BytesIO(data)).namelist()
        except zipfile.BadZipFile:
            return "zip-corrupt"
        if "xl/workbook.xml" in names:
            return "xlsx"
        if "word/document.xml" in names:
            return "docx"
        return "zip"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "ole (old xls/doc)"
    if data[:5] == b"%PDF-":
        return "pdf"
    if data[:16] == b"SQLite format 3\x00":
        return "sqlite"
    if b"\x00" in data[:2048]:
        return "binary"
    return "text"


def finding(cls, where, detail, recover="unknown", conf=0.7):
    return {"class": cls, "where": where, "detail": detail, "recoverability": recover, "confidence": conf}


def scan_xlsx(path):
    out = []
    try:
        z = zipfile.ZipFile(path)
        bad = z.testzip()
        if bad:
            out.append(finding("corrupted", bad, "zip member fails CRC", "partial"))
        sheets = [n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
        total_f = total_v = 0
        for s in sorted(sheets):
            root = ET.fromstring(z.read(s))
            for c in root.iter("{%s}c" % NS["m"]):
                ref = c.get("r")
                if c.get("t") == "e":
                    out.append(finding("corrupted", "%s!%s" % (s, ref), "error value cell", "needs sources", 0.9))
                if c.find("m:f", NS) is not None:
                    total_f += 1
                elif c.find("m:v", NS) is not None and c.get("t") not in ("s", "e"):
                    total_v += 1
        if sheets and total_f == 0 and total_v > 0:
            out.append(finding("missing", "all sheets",
                               "workbook has %d numeric values and no formulas: formulas were likely pasted over as values" % total_v,
                               "rebuild from sources", 0.8))
        if "xl/calcChain.xml" not in z.namelist() and total_f == 0:
            out.append(finding("undocumented", "xl/calcChain.xml", "no calculation chain survives", "none", 0.6))
    except (zipfile.BadZipFile, ET.ParseError) as e:
        out.append(finding("corrupted", "container", "cannot parse workbook: %s" % e.__class__.__name__, "unknown", 0.9))
    return out


def scan_text(data):
    out = []
    lines = data.split(b"\n")
    for i, ln in enumerate(lines, 1):
        try:
            ln.decode("utf-8")
        except UnicodeDecodeError:
            out.append(finding("corrupted", "line %d" % i, "bytes are not valid text; row unreadable", "none", 0.9))
    cols = [len(ln.split(b",")) for ln in lines if ln.strip()]
    if cols and max(cols) > 1 and len(set(cols)) > 1:
        common = max(set(cols), key=cols.count)
        for i, ln in enumerate(lines, 1):
            n = len(ln.split(b","))
            if ln.strip() and n != common:
                out.append(finding("inconsistent", "line %d" % i, "row has %d columns, most rows have %d" % (n, common), "partial", 0.6))
    return out


def scan_secrets(data):
    out = []
    for i, ln in enumerate(data.split(b"\n"), 1):
        for kind, rx in SECRETS:
            if rx.search(ln):
                out.append(finding("undocumented", "line %d" % i, "possible %s (value not recorded)" % kind, "n/a", 0.7))
    return out


def scan(case, in_dir, out_dir):
    num = case.split("-")[-1]
    os.makedirs(os.path.join(out_dir, "working"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "quarantine"), exist_ok=True)
    report, frags, gaps = [], [], []
    for name in sorted(os.listdir(in_dir)):
        p = os.path.join(in_dir, name)
        if not os.path.isfile(p):
            continue
        with open(p, "rb") as fh:
            data = fh.read()
        kind = sniff(data)
        fs = []
        ext = os.path.splitext(name)[1].lower().lstrip(".")
        if ext in ("xlsx", "docx") and kind != ext:
            fs.append(finding("inconsistent", name, "extension says %s but content is %s" % (ext, kind), "partial", 0.8))
        if kind == "xlsx":
            fs += scan_xlsx(p)
        if kind == "text":
            fs += scan_text(data)
        if kind in ("text", "binary"):
            fs += scan_secrets(data)
        quarantined = EICAR_MARK in data
        if quarantined:
            fs.append(finding("undocumented", name, "EICAR test marker found: quarantined, not executed", "n/a", 1.0))
        shutil.copyfile(p, os.path.join(out_dir, "quarantine" if quarantined else "working", name))
        if quarantined:
            status = "quarantined"
        elif any(f["class"] in ("missing", "corrupted") for f in fs):
            status = "damaged"
        else:
            status = "clean"
        report.append({"file": name, "detected_type": kind, "sha256": hashlib.sha256(data).hexdigest(),
                       "size": len(data), "status": status, "findings": fs})
        for f in fs:
            frags.append({"fragment_id": "F-%s-%03d" % (num, len(frags) + 1), "source_file": name, "location": f["where"],
                          "type": "clue", "confidence": f["confidence"], "notes": "%s: %s" % (f["class"], f["detail"])})
            if f["class"] in ("missing", "corrupted"):
                gaps.append({"gap_id": "G-%s-%02d" % (num, len(gaps) + 1), "what": "%s: %s" % (name, f["detail"]),
                             "why": f["class"], "status": "open",
                             "where_to_look": ["other files in the case folder", "exports", "older copies"]})
    sources = [r["file"] for r in report if r["status"] == "clean"]
    dr = {"case_id": case, "stage": "forensics", "files": report, "possible_source_files": sources}
    for fn, obj in (("damage_report.json", dr), ("fragments.json", frags), ("gaps.json", gaps)):
        with open(os.path.join(out_dir, fn), "w") as fh:
            json.dump(obj, fh, indent=2)
    return dr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    r = scan(a.case, a.in_dir, a.out_dir)
    print(json.dumps({"case_id": a.case, "files": len(r["files"]),
                      "quarantined": sum(f["status"] == "quarantined" for f in r["files"]),
                      "damaged": sum(f["status"] == "damaged" for f in r["files"])}))
