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
| Recovery Manager (Coordinator) | Owns each case: intake, quote, hand-offs, the rebuild-and-check loop (3 retries) and delivery | `naive/agents/recovery-manager/`, `naive/skills/front-desk-and-coordinator/` |
| Client-facing (Comms) | Intake, quote, questions to the client, status updates | Part of the Recovery Manager (`naive/lib/quote.py`) |
| Forensics / Salvage | Scans and quarantines first, never runs client files, extracts fragments | `naive/agents/forensics/`, `naive/skills/forensics-scanner/` |
| Context | Hunts surviving evidence and maps missing item → source → method | `naive/agents/context/`, `naive/skills/context-evidence/` |
| Mail Scout | Searches the client inboxes for the figures, rules and files a case is missing; reads mail only, never sends | `naive/agents/mail-scout/`, `naive/skills/mail-scout/` |
| Reconstruction | Rebuilds formulas and code from evidence; asks the client when two readings fit | `naive/agents/reconstruction/`, `naive/skills/reconstruction-toolkit/` |
| Validation | Checks rebuilds against private held-out tests, never repairs them, returns limited feedback | `verify/`, `naive/agents/validation/` |
| Deliverable | Packages the result, report and invoice for the client | Part of the Recovery Manager |

Agents pass structured messages (`{case_id, stage, kind, files, note}`) and share files through the Naive file library in one flat folder per case and stage (`C-0001-incoming`, `C-0001-rebuilt`, `C-0001-report`, ...), because folder names cannot contain "/". Shared tools live in the folder `tools`. See `docs/codecare-contracts.md`.

## What's in the repo

| Path | What | Owner |
|---|---|---|
| `data/public/` | Synthetic demo evidence: two Excel companies, the invoicing case and a harmless scanner test file | Tvisha |
| `data/generate.py` | Seeded generator for that evidence (`--check` proves it reproduces exactly) | Tvisha |
| `verify/` | Validation harness: recalculates workbooks with changed inputs, compares money to the cent, labels each item | Tvisha |
| `naive/agents/*/` | Naive agent configs for the six case agents: Recovery Manager, Forensics, Context, Mail Scout, Reconstruction, Validation | Team |
| `naive/skills/` | Agent skills: coordinator, forensics scanner, context evidence, Mail Scout, reconstruction toolkit, Excel formula engine, validation harness, self-audit | Team |
| `naive/lib/` | Tools agents run in their sandboxes: `formula_infer.py`, `backtest.py`, `probe_diff.py`, `reconcile.py`, the forensics scanners, `quote.py`, `cc.py` (writes case records) and `sync_records.py` (the records relay) | Team |
| `app/`, `db/schema.sql`, `web/` | Data Care app: records API, live board, case detail and ticket intake, on Neon | Andy |
| `tools/board`, `docs/agent-board.md` | Team message board for our coding agents | template |

## Try it

These run locally and were checked on the current code.

The Data Care app (records API and board) runs on an in-memory database:

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
| Validation ↔ agents hand-off, and records via `cc.py` | Live. Validation logs a verdict and one report item per cell. |
| Data Care app and records client | Live on Naive: board, case detail and ticket form, on Neon. App tests pass (10/10). |
| Context and Reconstruction agents | Live on Naive. Their tools are in `naive/lib/` and in the Naive file library folder `tools/`. |
| Reconstruction `backtest.py` and the invoicing dataset | Wired. The code case rebuilt the invoicing function and matched every readable invoice to the cent. |
| Recovery Manager, Forensics, Mail Scout | Live on Naive. The Recovery Manager also handles Comms and delivery: quote, the client's APPROVE, then the report and invoice. |
| End-to-end run on Naive | Done on live cases, from the client's email to delivery. C-0003 (Alderbank) passed Validation on the first try. |

## Safety rules we hold to

- **Hidden tests stay hidden.** Validation's held-out tests live only with the Validation owner and the Validation agent. They are gitignored and never shown to the Reconstruction agent.
- **Client files are never executed** outside a Naive sandbox. The scanner test file is the standard harmless EICAR marker.
- **Candidates are never repaired by the checker,** and a pass means "tested behaviour matches", not "the original was recovered verbatim".
- **No credentials in the repo.** Keys live in the Naive vault and are referenced by name.

## Team

Tvisha Vudanrao (@tvishavudanrao-hub): demo data, Validation · Balthazar Sauquet (@balthyZart): Context, Reconstruction · Andrei Jacques (@andrei-jacques): Data Care app, Neon · Anna Liu (@annathebest-creator): Recovery Manager · NWCodeStack (@NWCodeStack): Forensics, team lead

All companies, people and numbers in the demo data are synthetic.
