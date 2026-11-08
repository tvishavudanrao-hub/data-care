"""Pack the PUBLIC verifier code into one zip for the Naive file library folder `tools`.

    python -m verify.pack            # writes validation_tools.zip
    vetta file upload --file validation_tools.zip --folder tools --scope published

The Validation agent fetches it with find_files + fetch_file and unpacks it with
`python3 -m zipfile -e validation_tools.zip .`, the same way the other agents get
their tools. verify/hidden/ is NEVER packed: the `tools` folder is readable by every
agent, including Reconstruction. The private bundle reaches the Validation agent
by a separate, Validation-only route (see naive/skills/validation-harness/SKILL.md).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "verify/__init__.py", "verify/layout.py", "verify/schema.py", "verify/retry.py", "verify/engine.py",
    "verify/excel_verifier.py", "verify/code_verifier.py", "verify/sandbox.py", "verify/store.py",
    "verify/handoff.py", "verify/cli.py", "verify/requirements.txt", "verify/code_harness/sandbox_runner.py",
    "data/__init__.py", "data/public/code_a/invoicing.py", "naive/lib/cc.py",
]


def main(out: str = "validation_tools.zip") -> int:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in FILES:
            assert "hidden" not in rel
            z.write(ROOT / rel, rel)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    assert not any("hidden" in n for n in names), "private files must never be packed"
    print(f"wrote {out}: {len(names)} public files, no verify/hidden/")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
