#!/usr/bin/env python3
"""Replay the client's surviving records through a candidate rebuild.

    python3 backtest.py --script rebuilt/invoicing.py --records invoices.csv --mapping mapping.json --out backtest.json

Two kinds of mapping.json.

1. Function mode (a code module whose function was lost; the usual case for kind "code").
   The tool imports ONLY the rebuilt file, in a separate Python process with a timeout, and calls the function
   once per readable record:
{
  "id_column": "invoice_id",
  "call": {"function": "compute_discount",
           "args": ["{subtotal:decimal}", "{total_units:int}", "{customer_tier}", "{config}"]},
  "config": {"file": "discounts.yml", "loader": "load_config"},
  "returns": "Decimal",
  "compare": {"return": "discount"}
}
   "{col}" is the column's text, "{col:int}", "{col:decimal}", "{col:float}" convert it. "{config}" is the
   config file loaded by the rebuilt module's own loader (or by a small built-in YAML/JSON reader when the
   module has none, or when PyYAML is not installed). "returns" checks the type the contract promises.
   "compare" maps "return" (or "return.<key>" for a dict result) to the record column it must equal.

2. Script mode (a script that reads one JSON input file and prints JSON), unchanged from v1:
{
  "id_column": "invoice_id",
  "input": {"invoice_id": "{invoice_id}", "lines": [{"qty": 1, "unit_price": "{goods_subtotal}"}]},
  "args": ["--invoice", "{input_file}"],
  "compare": {"discount": "discount", "total": "total"}
}

Numbers must be equal exactly (157.4 equals 157.40; 157.404 does not equal 157.40, it is reported as
"not rounded to the cent"). Unreadable rows (bad bytes, wrong number of fields, a blank or unparseable value in
a column the mapping uses) are skipped and listed with the reason, never guessed. Blank lines are ignored.

Safety: the tool refuses to run the client's original file. It treats as original any file passed with
--original, the "original" path in the mapping, and a file with the script's name sitting next to the records.
It never imports anything by module name, does not write .pyc files into rebuilt/, and runs the candidate
from an empty temporary folder. Standard library only, Python 3.8+.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation

PLACEHOLDER = re.compile(r"\{([A-Za-z_][\w .-]*?)(?::(int|decimal|float|str))?\}")
BAD_CHAR = "�"


class MappingError(Exception):
    pass


class OriginalFileError(Exception):
    pass


# --------------------------------------------------------------------------- values

def parse_value(raw, typ):
    """Text from a record -> typed value. Raises ValueError when it cannot be read."""
    if typ in (None, "str"):
        return raw
    text = (raw or "").strip().replace(",", "").replace("$", "")
    if not text:
        raise ValueError("blank")
    if typ == "int":
        if not re.fullmatch(r"[-+]?\d+", text):
            raise ValueError("not a whole number: %r" % raw)
        return int(text)
    if typ == "float":
        return float(text)
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise ValueError("not a number: %r" % raw)
    if not d.is_finite():
        raise ValueError("not a finite number: %r" % raw)
    return d


def used_columns(template, found=None):
    """{column: type} for every placeholder in a template (dict/list/str)."""
    found = {} if found is None else found
    if isinstance(template, dict):
        for v in template.values():
            used_columns(v, found)
    elif isinstance(template, list):
        for v in template:
            used_columns(v, found)
    elif isinstance(template, str):
        for m in PLACEHOLDER.finditer(template):
            if m.group(1) not in ("config", "input_file"):
                found.setdefault(m.group(1), m.group(2) or "str")
    return found


def fill(template, row, extra=None):
    """Replace placeholders in one pass. A string that is exactly one typed placeholder becomes that type."""
    extra = extra or {}
    if isinstance(template, dict):
        return {k: fill(v, row, extra) for k, v in template.items()}
    if isinstance(template, list):
        return [fill(v, row, extra) for v in template]
    if not isinstance(template, str):
        return template
    whole = PLACEHOLDER.fullmatch(template)
    if whole and whole.group(1) in extra:
        return extra[whole.group(1)]
    if whole and whole.group(2) and whole.group(2) != "str":
        if whole.group(1) not in row:
            raise MappingError("the mapping uses {%s} but the records have no column %r" % (whole.group(1), whole.group(1)))
        return parse_value(row[whole.group(1)], whole.group(2))

    def sub(m):
        name = m.group(1)
        if name in extra:
            return str(extra[name])
        if name not in row:
            raise MappingError("the mapping uses {%s} but the records have no column %r" % (name, name))
        return row[name]
    return PLACEHOLDER.sub(sub, template)


def as_decimal(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        return parse_value(str(value), "decimal")
    except ValueError:
        return None


def compare(candidate, record):
    """None when they match exactly, else a short reason."""
    a, b = as_decimal(candidate), as_decimal(record)
    if a is None or b is None:
        return None if str(candidate).strip() == str(record).strip() else "different"
    if a == b:
        return None
    if a.as_tuple().exponent < -2 and abs(a - b) < Decimal("0.01"):
        return "not rounded to the cent"
    return "different"


def same(a, b):
    """Kept for older callers: True when two values match exactly (see compare)."""
    return compare(a, b) is None


# --------------------------------------------------------------------------- records

def read_records(path):
    """-> (header, [(line_number, raw_fields)]). Handles a BOM, blank lines and quoted multi-line fields."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.reader(f)
        header = None
        rows = []
        start = 1
        for raw in reader:
            line = start
            start = reader.line_num + 1
            if not raw or all(not v.strip() for v in raw):
                continue
            if header is None:
                header = [h.strip() for h in raw]
                continue
            rows.append((line, raw))
    if header is None:
        raise MappingError("%s has no header row" % path)
    return header, rows


def unreadable_reason(raw, header, used):
    if len(raw) != len(header):
        return "has %d fields, the header has %d" % (len(raw), len(header))
    if any(BAD_CHAR in v for v in raw):
        return "unreadable characters (U+FFFD)"
    row = dict(zip(header, raw))
    for col, typ in used.items():
        if col not in row:
            raise MappingError("the mapping uses {%s} but the records have no column %r" % (col, col))
        if typ != "str" and not row[col].strip():
            return "%s is blank" % col
        try:
            parse_value(row[col], typ)
        except ValueError as e:
            return "%s: %s" % (col, e)
    return None


# --------------------------------------------------------------------------- safety

def _digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def check_not_original(script, originals):
    """Refuse to run a client original: same file, or byte-identical copy."""
    if not os.path.isfile(script):
        raise OriginalFileError("candidate %s does not exist" % script)
    mine = _digest(script)
    for orig in originals:
        if not orig or not os.path.isfile(orig):
            continue
        if os.path.samefile(script, orig) or _digest(orig) == mine:
            raise OriginalFileError(
                "refusing to run %s: it is the client's original (%s), unchanged. The tools only run your rebuilt "
                "copy; copy the project into rebuilt/ and implement the missing piece there." % (script, orig))


def default_originals(script, records, mapping, extra):
    out = list(extra or [])
    if mapping.get("original"):
        out.append(mapping["original"])
    if records:
        out.append(os.path.join(os.path.dirname(os.path.abspath(records)), os.path.basename(script)))
    return out


def clean_env():
    env = dict(os.environ)
    for k in ("PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME", "PYTHONINSPECT"):
        env.pop(k, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


# --------------------------------------------------------------------------- function mode (harness)

HARNESS = r'''
import importlib.util, json, os, re, signal, sys, traceback, types
from decimal import Decimal
job = json.load(open(sys.argv[1], encoding="utf-8"))
real_stdout = sys.stdout
sys.stdout = sys.stderr            # the candidate's own prints must not mix with our results
here = os.getcwd()
sys.path[:] = [p for p in sys.path if p not in ("", ".", here)]
sys.path.insert(0, os.path.dirname(job["script"]))
notes = []

def strip_comment(line):
    q = None
    for i, ch in enumerate(line):
        if q:
            if ch == q: q = None
        elif ch in "'\"": q = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"): return line[:i]
    return line

def scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"": return v[1:-1]
    low = v.lower()
    if low in ("null", "~", ""): return None
    if low in ("true", "yes", "on"): return True
    if low in ("false", "no", "off"): return False
    if re.fullmatch(r"[-+]?\d+", v): return int(v)
    if re.fullmatch(r"[-+]?(\d+\.\d*|\.\d+|\d+)([eE][-+]?\d+)?", v): return float(v)
    if v.startswith("[") and v.endswith("]"):
        return [scalar(x) for x in v[1:-1].split(",") if x.strip()]
    if v == "{}": return {}
    return v

def mini_yaml(text):
    if hasattr(text, "read"): text = text.read()
    lines = []
    for raw in str(text).splitlines():
        s = strip_comment(raw).rstrip()
        if s.strip() and s.strip() not in ("---", "..."):
            lines.append([len(s) - len(s.lstrip(" ")), s.strip()])
    pos = [0]
    def is_item(s): return s == "-" or s.startswith("- ")
    def block(ind):
        if pos[0] < len(lines) and is_item(lines[pos[0]][1]): return seq(ind)
        return mapping(ind)
    def seq(ind):
        out = []
        while pos[0] < len(lines) and lines[pos[0]][0] == ind and is_item(lines[pos[0]][1]):
            s = lines[pos[0]][1]
            item = s[1:].lstrip()
            if not item:
                pos[0] += 1
                out.append(block(lines[pos[0]][0]) if pos[0] < len(lines) and lines[pos[0]][0] > ind else None)
            elif re.match(r"^[^'\"\[{][^:]*:(\s|$)", item):
                lines[pos[0]] = [ind + len(s) - len(item), item]
                out.append(mapping(ind + len(s) - len(item)))
            else:
                pos[0] += 1
                out.append(scalar(item))
        return out
    def mapping(ind):
        out = {}
        while pos[0] < len(lines) and lines[pos[0]][0] == ind and not is_item(lines[pos[0]][1]):
            s = lines[pos[0]][1]
            m = re.match(r"^(\"[^\"]*\"|'[^']*'|[^:]+?)\s*:(\s+(.*))?$", s)
            if not m: raise ValueError("built-in YAML reader cannot read: %r" % s)
            key = scalar(m.group(1)); rest = (m.group(3) or "").strip()
            pos[0] += 1
            if rest:
                out[key] = scalar(rest)
            elif pos[0] < len(lines) and (lines[pos[0]][0] > ind or (lines[pos[0]][0] == ind and is_item(lines[pos[0]][1]))):
                out[key] = block(lines[pos[0]][0])
            else:
                out[key] = None
        return out
    data = block(lines[0][0]) if lines else None
    if pos[0] != len(lines): raise ValueError("built-in YAML reader stopped at: %r" % lines[pos[0]][1])
    return data

def yaml_shim():
    m = types.ModuleType("yaml")
    class YAMLError(Exception): pass
    m.YAMLError = YAMLError
    m.safe_load = mini_yaml
    m.load = lambda stream, Loader=None: mini_yaml(stream)
    m.SafeLoader = m.FullLoader = m.Loader = object
    m.__datacare_shim__ = True
    return m

def load_candidate():
    for attempt in (1, 2):
        spec = importlib.util.spec_from_file_location("datacare_candidate", job["script"])
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            return mod
        except ModuleNotFoundError as e:
            if attempt == 1 and e.name == "yaml":
                sys.modules["yaml"] = yaml_shim()
                notes.append("PyYAML is not installed here; used the built-in YAML reader for the config")
                continue
            raise

def decode(v, config):
    if isinstance(v, dict) and "$decimal" in v: return Decimal(v["$decimal"])
    if isinstance(v, dict) and v.get("$config"): return config
    if isinstance(v, dict): return {k: decode(x, config) for k, x in v.items()}
    if isinstance(v, list): return [decode(x, config) for x in v]
    return v

def encode(v):
    if isinstance(v, dict): return {"type": "dict", "value": {str(k): encode(x) for k, x in v.items()}}
    return {"type": type(v).__name__, "value": None if v is None else str(v)}

class Timeout(Exception): pass
def on_alarm(signum, frame): raise Timeout()
use_alarm = hasattr(signal, "setitimer")
if use_alarm: signal.signal(signal.SIGALRM, on_alarm)

out = {"results": {}, "notes": notes, "fatal": None}
try:
    mod = load_candidate()
    fn = getattr(mod, job["function"], None)
    if not callable(fn): raise AttributeError("the rebuilt module has no function %r" % job["function"])
    config = None
    cfg = job.get("config")
    if cfg:
        loader = getattr(mod, cfg.get("loader") or "", None)
        if callable(loader):
            config = loader(cfg["file"])
        elif cfg["file"].lower().endswith(".json"):
            config = json.load(open(cfg["file"], encoding="utf-8"))
        else:
            config = mini_yaml(open(cfg["file"], encoding="utf-8").read())
            notes.append("config read with the built-in YAML reader")
    for call in job["calls"]:
        try:
            if use_alarm: signal.setitimer(signal.ITIMER_REAL, job["per_call_timeout"])
            value = fn(*decode(call.get("args", []), config), **decode(call.get("kwargs", {}), config))
            if use_alarm: signal.setitimer(signal.ITIMER_REAL, 0)
            out["results"][str(call["key"])] = encode(value)
        except Timeout:
            out["results"][str(call["key"])] = {"error": "timed out after %ss" % job["per_call_timeout"]}
        except Exception as e:
            if use_alarm: signal.setitimer(signal.ITIMER_REAL, 0)
            out["results"][str(call["key"])] = {"error": "%s: %s" % (type(e).__name__, e)}
except BaseException as e:
    out["fatal"] = "%s: %s" % (type(e).__name__, e)
    out["trace"] = traceback.format_exc()[-1500:]
with open(sys.argv[2], "w", encoding="utf-8") as fh:
    json.dump(out, fh)
'''


def encode_arg(v):
    if isinstance(v, Decimal):
        return {"$decimal": str(v)}
    if isinstance(v, dict):
        return {k: encode_arg(x) for k, x in v.items()}
    if isinstance(v, list):
        return [encode_arg(x) for x in v]
    return v


def call_function(script, function, calls, config=None, timeout=10):
    """Run calls [{"key", "args", "kwargs"}] against the rebuilt module in a subprocess.

    Returns ({key: {"type", "value"} | {"error"}}, notes, fatal_error_or_None)."""
    script = os.path.abspath(script)
    work = tempfile.mkdtemp(prefix="backtest_")
    job_path, out_path = os.path.join(work, "job.json"), os.path.join(work, "out.json")
    cfg = None
    if config:
        cfg = {"file": os.path.abspath(config["file"]), "loader": config.get("loader")}
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump({"script": script, "function": function, "config": cfg, "per_call_timeout": timeout,
                   "calls": [{"key": c["key"], "args": encode_arg(c.get("args", [])),
                              "kwargs": encode_arg(c.get("kwargs", {}))} for c in calls]}, f)
    run_dir = os.path.join(work, "run")
    os.mkdir(run_dir)
    total = timeout * max(1, len(calls)) + 20
    try:
        p = subprocess.run([sys.executable, "-B", "-c", HARNESS, job_path, out_path], cwd=run_dir, env=clean_env(),
                           capture_output=True, text=True, timeout=total)
        if not os.path.exists(out_path):
            tail = (p.stderr.strip().splitlines() or ["exit %d" % p.returncode])[-1]
            return {}, [], "the rebuilt module crashed: %s" % tail
        with open(out_path, encoding="utf-8") as f:
            out = json.load(f)
        return out["results"], out.get("notes", []), out.get("fatal")
    except subprocess.TimeoutExpired:
        return {}, [], "timed out after %ss" % total
    finally:
        for name in (job_path, out_path):
            if os.path.exists(name):
                os.remove(name)
        try:
            os.rmdir(run_dir)
            os.rmdir(work)
        except OSError:
            pass


def resolve(path, base):
    if not path or os.path.isabs(path) or os.path.exists(path):
        return path
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


# --------------------------------------------------------------------------- script mode (v1)

def run_candidate(script, args, payload, timeout):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(payload, f, default=str)
        path = f.name
    try:
        cmd = [sys.executable, "-B", os.path.abspath(script)] + [a.replace("{input_file}", path) for a in args]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=clean_env(),
                           cwd=os.path.dirname(os.path.abspath(script)))
        if p.returncode != 0:
            return None, (p.stderr.strip().splitlines() or ["exit %d" % p.returncode])[-1]
        text = p.stdout.strip()
        try:
            return json.loads(text), None
        except ValueError:
            for line in reversed(text.splitlines()):          # tolerate debug prints before the JSON line
                try:
                    return json.loads(line), None
                except ValueError:
                    continue
            return None, "output was not JSON"
    except subprocess.TimeoutExpired:
        return None, "timed out after %ss" % timeout
    finally:
        os.remove(path)


# --------------------------------------------------------------------------- backtest

def pick(out, field):
    """Value for a compare key from a function result {"type","value"} (supports return.<key>)."""
    node = out
    for part in field.split(".")[1:]:
        if node.get("type") != "dict" or part not in node["value"]:
            return {"type": "missing", "value": None}
        node = node["value"][part]
    return node


def backtest(script, records, mapping, timeout=10, originals=None, mapping_dir="."):
    check_not_original(script, default_originals(script, records, mapping, originals))
    if "compare" not in mapping or not mapping["compare"]:
        raise MappingError("the mapping needs a \"compare\" map: output -> record column")
    header, body = read_records(records)
    mode = "function" if "call" in mapping else "script"
    template = mapping["call"] if mode == "function" else mapping["input"]
    used = used_columns(template)
    for col in mapping["compare"].values():
        used.setdefault(col, "decimal")
    idcol = mapping.get("id_column", "")
    if idcol and idcol not in header:
        raise MappingError("id_column %r is not a column of %s (columns: %s)" % (idcol, records, ", ".join(header)))
    result = {"script": script, "records": records, "mode": mode, "rows_total": len(body), "rows_checked": 0,
              "unreadable_rows": [], "unreadable": [], "passed": 0, "failed": 0, "mismatches": [], "errors": [],
              "passed_ids": [], "notes": []}
    todo = []
    for n, raw in body:
        reason = unreadable_reason(raw, header, used)
        rid = raw[header.index(idcol)].strip() if idcol and len(raw) == len(header) else "row %d" % n
        if reason:
            result["unreadable_rows"].append(n)
            result["unreadable"].append({"row": n, "id": rid, "reason": reason})
            continue
        todo.append((n, rid, dict(zip(header, raw))))
    outs = {}
    if mode == "function":
        call = mapping["call"]
        config = None
        if mapping.get("config"):
            config = dict(mapping["config"])
            config["file"] = resolve(config["file"], mapping_dir)
            if not os.path.exists(config["file"]):
                raise MappingError("config file %s not found" % config["file"])
        calls = [{"key": n, "args": fill(call.get("args", []), row, {"config": {"$config": True}}),
                  "kwargs": fill(call.get("kwargs", {}), row, {"config": {"$config": True}})} for n, _, row in todo]
        res, notes, fatal = call_function(script, call["function"], calls, config, timeout)
        result["notes"] += notes
        if fatal:
            result["fatal"] = fatal
        for n, _, _ in todo:
            outs[n] = res.get(str(n), {"error": fatal or "no result"})
    for n, rid, row in todo:
        result["rows_checked"] += 1
        if mode == "function":
            out = outs[n]
            err = out.get("error")
        else:
            out, err = run_candidate(script, mapping.get("args", ["--invoice", "{input_file}"]),
                                     fill(mapping["input"], row), timeout)
        if err:
            result["failed"] += 1
            result["errors"].append({"row": n, "id": rid, "error": err})
            continue
        bad = []
        for field, col in mapping["compare"].items():
            if mode == "function":
                got = pick(out, field)
                value = got.get("value")
                if mapping.get("returns") and field == "return" and got.get("type") != mapping["returns"]:
                    bad.append({"row": n, "id": rid, "field": field, "record": row.get(col), "candidate": value,
                                "why": "returned %s, the contract says %s" % (got.get("type"), mapping["returns"])})
                    continue
            else:
                value = out.get(field)
            why = compare(value, row.get(col))
            if why:
                bad.append({"row": n, "id": rid, "field": field, "record": row.get(col), "candidate": value, "why": why})
        if bad:
            result["failed"] += 1
            result["mismatches"].extend(bad)
        else:
            result["passed"] += 1
            result["passed_ids"].append(rid)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--script", required=True, help="your rebuilt file (never the client's original)")
    p.add_argument("--records", required=True)
    p.add_argument("--mapping", required=True)
    p.add_argument("--out")
    p.add_argument("--timeout", type=int, default=10, help="seconds per record")
    p.add_argument("--original", action="append", default=[], help="client original(s) the tool must never run")
    a = p.parse_args()
    with open(a.mapping, encoding="utf-8") as f:
        mapping = json.load(f)
    try:
        r = backtest(a.script, a.records, mapping, a.timeout, a.original,
                     os.path.dirname(os.path.abspath(a.mapping)))
    except (MappingError, OriginalFileError) as e:
        print("backtest: %s" % e, file=sys.stderr)
        sys.exit(2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2)
    print("backtest: %d of %d readable rows match; %d unreadable rows skipped (%s)"
          % (r["passed"], r["rows_checked"], len(r["unreadable_rows"]),
             "; ".join("row %d %s: %s" % (u["row"], u["id"], u["reason"]) for u in r["unreadable"]) or "none"))
    if r.get("fatal"):
        print("  the rebuilt module could not run: %s" % r["fatal"])
    for note in r["notes"]:
        print("  note: %s" % note)
    for m in r["mismatches"][:10]:
        print("  row %s %s: %s is %s in the record, %s in the rebuild (%s)"
              % (m["row"], m["id"], m["field"], m["record"], m["candidate"], m.get("why", "different")))
    for e in r["errors"][:5]:
        print("  row %s %s: error %s" % (e["row"], e["id"], e["error"]))
    sys.exit(0 if r["failed"] == 0 and r["rows_checked"] > 0 else 1)


if __name__ == "__main__":
    main()
