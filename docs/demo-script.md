# Demo script (draft, Nash's Claude: Nash edits presenters and timing)

Demo length: 4 minutes (proposal). Presenter: [Nash to assign]. Backup video: [Anna: link].

The one sentence: We're an autonomous AI recovery company that reconstructs lost or damaged business assets, not just from the files themselves, but from the information, relationships and context that survive across an organization.

Rules for the stage: claim only what runs. Every number below comes from a real Naive run on the demo data (Alderbank, case C-0101). If a number on screen differs, say the screen's number.

| Time | Step | What we show | What we say | If it fails |
|---|---|---|---|---|
| 0:00 | Hook | The damaged Alderbank model: numbers where formulas used to be, a #REF!, blank cells | "Someone pasted over every formula. The numbers are still there, nobody knows how they were made." | Show the screenshot in the backup video |
| 0:20 | Client emails us | The client email with the damaged .xlsx arriving at datacare-recover@agentmail.to; the case opening (C-0001) on the live Data Care board | "A client emails their damaged file. A company of AI agents takes it from there." | Open the board page, show the already-open case |
| 0:45 | Forensics | The damage report: formulas pasted over as values, the error cell, nothing run, the harmless test marker quarantined | "First agent only reads. It never runs a client file, and it tells us what is broken and where the source data might be." | Show damage_report.json from the case folder |
| 1:15 | Context + Mail Scout | The evidence map: the surviving ERP export, the board report, the CFO's email with the discount rule; a gap the Mail Scout looks for in old email | "Second agent finds the data the model was built from, scattered across files and email. It does not guess." | Show evidence.json |
| 1:50 | Reconstruction | The rebuilt model: 81 formulas, labeled recovered / reconstructed and tested / reconstructed but untested / unresolved; the one cell left unresolved (Q1 opex) with the exact question for the client | "It rebuilds only what the surviving data proves. Where nothing proves it, it says unresolved and drafts the email asking the client." | Open report_draft.md |
| 2:30 | Validation | The case's `report.md` opening with "Independent validation: Passed" and the counts (27 recovered / 81 reconstructed and tested / 1 unresolved); then `docs/demo/validation-proof.html` | "Matching the old numbers isn't proof. A separate agent changes the inputs (prices, units, discount thresholds, empty quarters) and checks every cell to the cent against answers the builder never saw. Three of these four wrong rebuilds reproduce every historical number, and it catches all of them. A wrong rebuild goes back, at most three times." | Open `docs/demo/validation-proof.html` (works offline) or the backup clip |
| 3:00 | Autonomy + cost | The client's APPROVE reply to the quote; cost per case and "Humans stepped in" on the board | "The only approval is the client's, on the quote. After that nobody on our team touches the case, and every step's real cost is on the board." | Show the cost line from the case events |
| 3:25 | Second asset | The code case (C-0103): a lost invoicing function rebuilt, 29 of 29 readable invoices matching to the cent, the damaged invoice reported as a gap | "Same pipeline, different file type. It reported the unreadable invoice as unknown instead of inventing it." | Skip to the close |
| 3:45 | Close | The Data Care board | "Accounting records, documents and databases come next. The pipeline stays the same, only the parsers change." | — |

Before going on stage:
- [ ] Demo data reset to the starting state (new case numbers; Alderbank files in the datacare-recover@agentmail.to inbox, not already processed)
- [ ] Credits checked (the Naive dashboard); the Recovery Manager's per-task cap is $3 and its daily cap $30; Validation is $1 per task and $5 per month, so check it will cover a full run
- [ ] AgentMail bridge running on Anna's Mac; relay running on Andrei's Mac; Data Care board open and live
- [ ] No approval is needed on stage: every email sends on its own and mailbox search runs in the bridge. The presenter only plays the client and replies APPROVE to the quote (or sends the test email from the client's address)
- [ ] Logged in, tabs open in order, notifications off
- [ ] Backup video downloaded locally (plus Tvisha's clips: Validation proof, and ticket → connect storage → "what we read")
- [ ] `docs/demo/validation-proof.html` open in a tab (numbers come from real verifier runs; no hidden answers on it)
- [ ] Do not show: `verify/hidden/`, API keys, vault pages, real client data

Open items for the team before the demo:
- Presenter assignments and who clicks which approval (Nash).
- Exact timings once the full rehearsal runs (Balthazar's end-to-end rehearsal).
- Confirm every number above against the final run; the script only states what the C-0101 and C-0103 runs showed.
