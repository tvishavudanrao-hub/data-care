# Data Care

We're building an autonomous AI recovery company that reconstructs lost or damaged business assets, not just from the files themselves, but from the information, relationships and context that survive across an organization.

Built at the Naive Autonomous Company Hackathon (Y Combinator, San Francisco, Nov 7 to 8, 2026) with Naive agents.

**Investigate → Recover → Infer → Reconstruct → Validate.** Every result is labeled with exactly one of: **recovered**, **reconstructed and tested**, **reconstructed but untested** or **unresolved**. Missing facts are flagged, never invented.

## The two demos

1. **Excel recovery (main demo).** A company's 8-quarter financial model has lost its formulas: they were pasted over as values, and some cells are blank or show `#REF!`.
   - **Evidence that survives:** a board report, an ERP export and an email from the CFO.
   - **What happens:** agents rebuild the formulas from that evidence. A separate Validation agent then changes the inputs and checks that the rebuilt model still gives the right answers on scenarios the rebuilder never saw.
2. **Code recovery.** An invoicing script has lost its discount logic. It is rebuilt from the surviving invoices, the config file and the changelog, then checked against held-out invoices.

A second company with a **different** discount rule shows the agents aren't tuned to one case.

## The agents

| Agent | What it does | In this repo |
|---|---|---|
| Recovery Manager (Coordinator) | Owns each case, hands off stages, runs the rebuild-and-check loop (3 retries), escalates to a human | not yet |
| Client-facing (Comms) | Intake, quote, questions to the client, status updates | not yet |
| Forensics / Salvage | Scans and quarantines first, never runs client files, extracts fragments | not yet |
| Context | Hunts surviving evidence and maps missing item → source → method | `naive/agents/context/` |
| Reconstruction | Rebuilds formulas and code from evidence; asks the client when two readings fit | `naive/agents/reconstruction/`, `naive/skills/reconstruction-toolkit/` |
| Validation | Checks rebuilds against private held-out tests, never repairs them, returns limited feedback | `verify/`, `naive/agents/validation/` |
| Deliverable | Packages the result, report and invoice, waits for human approval | not yet |

Agents pass structured messages (`{case_id, stage, kind, files, note}`) and share files through the Naive file library in one flat folder per case and stage (`C-0001-incoming`, `C-0001-rebuilt`, `C-0001-report`, ...), because folder names cannot contain "/". Shared tools live in the folder `tools`. See `docs/codecare-contracts.md`.

## What's in the repo

| Path | What | Owner |
|---|---|---|
| `data/public/` | Synthetic demo evidence: two Excel companies, the invoicing case and a harmless scanner test file | Tvisha |
| `data/generate.py` | Seeded generator for that evidence (`--check` proves it reproduces exactly) | Tvisha |
| `verify/` | Validation harness: recalculates workbooks with changed inputs, compares money to the cent, labels each item | Tvisha |
| `naive/agents/*/` | Naive agent configs: Context and Reconstruction (exported), Validation (written, not deployed) | Balthazar, Tvisha |
| `naive/skills/` | Agent skills: the Reconstruction toolkit and the Validation harness | Balthazar, Tvisha |
| `naive/lib/` | Tools agents run in their sandboxes: `backtest.py`, `probe_diff.py`, `reconcile.py`, and `cc.py` (writes case records) | Balthazar, Andy |
| `app/`, `db/schema.sql` | Code Care app: records API plus the live board, on Neon | Andy |
| `tools/board`, `docs/agent-board.md` | Team message board for our coding agents | template |

## Try it

These run locally and were checked on the current code.

The Code Care app (records API and board) runs on an in-memory database:

```bash
cd app && npm install
```

```bash
node --test test/api.test.js
```

```bash
PORT=8787 CC_API_TOKEN=dev node server.js
```

The board is then at http://127.0.0.1:8787.

The `cc.py` client, end to end against the app:

```bash
python3 naive/lib/test_cc.py
```

Check that the demo evidence matches the seeded generator. This needs the private bundle, which only the Validation owner has:

```bash
python -m data.generate --check
```

The Validation self-test also needs the private bundle:

```bash
pip install -r verify/requirements.txt
```

```bash
python -m verify.selftest
```

## Status

| Piece | State |
|---|---|
| Demo data, companies A and B plus the invoicing case | Done, reproducible |
| Validation harness, Excel case | Works locally against known test candidates. A correct model passes. A wrong discount rule, pasted values, an invented number, and company A's rules applied to company B all fail. |
| Validation harness, code case | Static safety checks work. Running the rebuilt code waits on a Naive sandbox. |
| Validation ↔ agents hand-off, and records via `cc.py` | In review ([PR 5](https://github.com/tvishavudanrao-hub/data-care/pull/5)). Tested against the app's in-memory database. |
| Code Care app and records client | Tests pass locally (API 5/5, `cc.py` 4/4). Not yet deployed on Naive or connected to Neon. |
| Context and Reconstruction agents | Configs exported. The Excel tools the toolkit names (`context_scan.py`, `formula_infer.py`) are not in the repo yet. |
| Reconstruction `backtest.py` and the invoicing dataset | Not wired together yet. They expect different invoice columns. |
| Recovery Manager, Comms, Forensics, Deliverable | Not in the repo yet |
| End-to-end run on Naive | Not done yet |

## Safety rules we hold to

- **Hidden tests stay hidden.** Validation's held-out tests live only with the Validation owner and the Validation agent. They are gitignored and never shown to the Reconstruction agent.
- **Client files are never executed** outside a Naive sandbox. The scanner test file is the standard harmless EICAR marker.
- **Candidates are never repaired by the checker,** and a pass means "tested behaviour matches", not "the original was recovered verbatim".
- **No credentials in the repo.** Keys live in the Naive vault and are referenced by name.

## Team

Tvisha Vudanrao (@tvishavudanrao-hub): demo data, Validation · Balthazar Sauquet (@balthyZart): Context, Reconstruction · Andrei Jacques (@andrei-jacques): Code Care app, Neon · Anna Liu (@annathebest-creator) · NWCodeStack (@NWCodeStack)

All companies, people and numbers in the demo data are synthetic.
