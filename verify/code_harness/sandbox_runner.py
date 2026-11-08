"""RUNS ONLY INSIDE AN AUTHORIZED NAIVE SANDBOX. Never run this on a laptop or CI.

Uploaded into the Validation sandbox together with the candidate invoicing.py
and cases_input.json (inputs only; expected results never enter the sandbox,
because the candidate code runs here and could read them).

    python sandbox_runner.py invoicing.py cases_input.json > outputs.json

Prints one JSON object: {"outputs": {case_id: {"discount": "...", "net_total": "..."} | {"error": "..."}}}
"""

import importlib.util
import json
import sys
from decimal import Decimal


def main(candidate_path, cases_path):
    spec = importlib.util.spec_from_file_location("candidate_invoicing", candidate_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cases = json.load(open(cases_path))["cases"]
    out = {}
    for c in cases:
        i = c["input"]
        try:
            sub = Decimal(i["subtotal"])
            d = mod.compute_discount(sub, int(i["total_units"]), i["customer_tier"], i["config"])
            out[c["id"]] = {"discount": str(d), "net_total": str(sub - Decimal(d))}
        except Exception as exc:  # report, never hide
            out[c["id"]] = {"error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps({"outputs": out}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
