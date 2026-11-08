# How Data Care runs without people, and how an admin can look in

Data Care is an autonomous AI company. A client emails a damaged or incomplete asset; a team of Naive agents quotes the job, gets the client's approval by email, investigates, rebuilds what the surviving data supports, checks the result against answers it never saw, and delivers a report. **No human step is necessary anywhere in that loop.** The repository and the team board are here for judges and admins to read. Admins may look at any email, client or session at any time; nothing waits on them.

## Who does what

| Stage | Who | Where it runs |
|---|---|---|
| Intake and quote | Recovery Manager, using `naive/lib/quote.py` and `naive/pricing/pricing.json` | Naive agent; mail through AgentMail |
| Client approval | The client replies APPROVE (or APPROVE A / APPROVE B for the two-option small-business quote); the Recovery Manager reads it with `quote.py reply` | Email thread |
| Diagnose and sanitize files | Forensics Agent (`naive/lib/forensics_scan.py`): static checks only, never runs a client file | Naive agent sandbox |
| Find the surviving source data | Context Agent | Naive agent sandbox |
| Rebuild | Reconstruction Agent: only what the surviving sources prove; everything else is reported as unresolved | Naive agent sandbox |
| Check | Validation Agent, holding answers the builder never saw | Naive agent; private checks stay on its own computer |
| Records and live board | Data Care app on Neon, `naive/lib/cc.py` | Hosted app |

Every report item carries one of four labels: recovered, reconstructed and tested, reconstructed but untested, unresolved. We never invent a value that no source supports.

## Rails the agents keep without being asked

- No secret or credential is ever written into an email, file, log or message.
- Email goes only to the sender of the client's thread or to a fixed allowlist of our own inboxes.
- Every agent has a cost cap per run, per day or per month.
- Hidden validation examples are visible to the Validation agent only.
- A client file is never run outside the Naive sandbox. Client email and files are data, never instructions.
- Every outbound email has a send-once marker so a retried session cannot mail twice.

## Where an admin can look (read-only, optional)

- **Emails:** the threads in the AgentMail inboxes `codecare-recover@agentmail.to` (clients), `codecare-clinic@agentmail.to` (clinic checkups) and the `datacare-supplier-*` inboxes (simulated suppliers).
- **Sessions:** `vetta session list` shows every agent run; `vetta session get <session id>` and `vetta session events --session <session id>` show what an agent did, tool by tool, with its cost.
- **Case files:** `vetta file list --folder <case id>-report` (also `-incoming`, `-working`, `-evidence`, `-rebuilt`).
- **Cases, cost per case and verdicts:** the Data Care board (the hosted app) and the Neon records behind it.
- **Prices:** `naive/pricing/pricing.json`. Rates are placeholders until real costs are read off the board.

## Honest status

Parts of the running loop still depend on a team member's laptop (the mailbox bridge and the records relay). They are being moved into Naive so the company keeps running with every laptop closed. Naive itself still asks a person before an agent reads people's mail, so no agent does: the bridge reads the mailbox and hands the Recovery Manager files.
