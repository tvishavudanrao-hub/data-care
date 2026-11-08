# Demo script (draft, Nash's Claude: Nash edits presenters and timing)

Demo length: 4 minutes (proposal). Presenter: [Nash to assign]. Backup video: [Anna: link].

The one sentence: We're an autonomous AI recovery company that reconstructs lost or damaged business assets, not just from the files themselves, but from the information, relationships and context that survive across an organization.

Rules for the stage: claim only what runs. The numbers below come from real Naive runs on the demo data (Excel: Alderbank, C-0101, started directly by Balthazar; code: C-0103). The full email -> bridge -> Recovery Manager -> Forensics -> Context -> client question -> client answer -> Reconstruction -> Validation pass path has run end to end on C-0001 (Anna's test sheet), not yet on Alderbank. Delivery has been drafted with attachments but not yet approved and sent: do not say "delivered" until a rehearsal shows it. If a number on screen differs, say the screen's number.

| Time | Step | What we show | What we say | If it fails |
|---|---|---|---|---|
| 0:00 | Hook | The damaged Alderbank model: numbers where formulas used to be, a #REF!, blank cells | "Someone pasted over every formula. The numbers are still there, nobody knows how they were made." | Show the screenshot in the backup video |
| 0:20 | Client emails us | The client email with the damaged .xlsx arriving at the recover inbox; the case opening (C-000N, the next free id; C-0001 was Anna's own test sheet) on the live Data Care board | "A client emails their damaged file. A company of AI agents takes it from there." | Open the board page, show the already-open case |
| 0:45 | Forensics | The damage report: formulas pasted over as values, the error cell, nothing run, the harmless test marker quarantined | "First agent only reads. It never runs a client file, and it tells us what is broken and where the source data might be." | Show damage_report.json from the case folder |
| 1:15 | Context + Mail Scout | The evidence map: the surviving ERP export, the board report, the CFO's email with the discount rule; a gap the Mail Scout looks for in old email | "Second agent finds the data the model was built from, scattered across files and email. It does not guess." | Show evidence.json |
| 1:50 | Reconstruction | The rebuilt model: 81 formulas, labeled recovered / reconstructed and tested / reconstructed but untested / unresolved; the one cell left unresolved (Q1 opex) with the exact question for the client | "It rebuilds only what the surviving data proves. Where nothing proves it, it says unresolved and drafts the email asking the client." | Open report_draft.md |
| 2:15 | Client question | The one exact question the Recovery Manager emails the client (a person approves it), the client's reply, and the rebuilt total changing (on C-0001: 34,400 to 56,831, then Validation recalculated all 62 formulas, 0 failures) | "When the data can't prove an answer, it asks the client instead of guessing." | Show the C-0001 emails from the backup video |
| 2:30 | Validation | The auditor recalculating the workbook on inputs the builder never saw; the verdict | "A separate agent, holding answers the builder never saw, checks the work. A wrong rebuild gets sent back, at most three times." | Show the verdict row on the board |
| 3:00 | Human gate + cost | A person approving the delivery email in Naive; cost per case and "Humans stepped in" on the board | "Nothing goes to a client without a person's approval. Every step has a real cost, shown here." | Show the cost line from the case events |
| 3:25 | Second asset | The code case (C-0103): a lost invoicing function rebuilt, 29 of 29 readable invoices matching to the cent, the damaged invoice reported as a gap | "Same pipeline, different file type. It reported the unreadable invoice as unknown instead of inventing it." | Skip to the close |
| 3:45 | Close | The Data Care board | "Accounting records, documents and databases come next. The pipeline stays the same, only the parsers change." | — |

Before going on stage:
- [ ] Demo data reset to the starting state. The bridge marks each processed email `dc-processed` and never reads it again, so the Alderbank request email must be sent fresh just before the demo
- [ ] Approve each pending send with the exact `vetta session confirm --session <ses_id> --tool-call <id> --allow` line, not by clicking in the Naive app (a click once approved the wrong email)
- [ ] Credits checked (the Naive dashboard); each agent's per-task cap is $1
- [ ] AgentMail bridge running on Anna's Mac; relay running on Andrei's Mac; Data Care board open and live
- [ ] A person is ready to approve the delivery email in the Naive app (also each Mail Scout mail read)
- [ ] Logged in, tabs open in order, notifications off
- [ ] Backup video downloaded locally
- [ ] Do not show: `verify/hidden/`, API keys, vault pages, real client data

Open items for the team before the demo:
- Presenter assignments and who clicks which approval (Nash).
- Exact timings once the full rehearsal runs (Balthazar's end-to-end rehearsal).
- Confirm every number above against the final run; the script only states what the C-0101 and C-0103 runs showed.
