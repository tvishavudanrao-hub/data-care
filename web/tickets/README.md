# Ticket intake (bare bones)

This is a public form where a customer describes what they lost. It's self-contained, so the Data Care app can adopt it later without touching anything else. Owner: Tvisha. It's meant to be wired into Andy's `app/`.

## What a customer sees

They open `/tickets` and fill in:
- name and email
- company (optional)
- what was lost (spreadsheet, code or other)
- where they use it, so we send the right install steps
- what happened
- consent to be emailed

They get a reference like `T-20261108-DQN9E`.

- **No file uploads.** Client files may be infected, so they come in later through the case flow, where Forensics scans them first.
- **No email is sent here.** The quote and install-steps email goes out from the Recovery Manager after a person approves it.

## Routes

| Route | Who | What |
|---|---|---|
| `GET /tickets` | public | the form |
| `POST /api/tickets` | public | submit (JSON or form-encoded); 400 with a plain-English reason, 413 if too long |
| `GET /api/tickets?status=new` | `x-cc-token` | list tickets (newest first, 200 max) |
| `PATCH /api/tickets/<id>` | `x-cc-token` | set `status` (new, quoted, in_progress, closed), `quote_usd`, `case_id` |

**Spam:** a hidden "website" field catches bots. Their submissions look accepted, but nothing is stored.

## Try it locally

```bash
node web/tickets/server.js
```

Open http://127.0.0.1:8790/tickets. It uses an in-memory store, and the team routes use the token `dev`.

```bash
cd web/tickets && npm test
```

The test suite has 11 tests. One runs the real SQL on Postgres (PGlite), which needs `npm install` in `app/` first.

## Wiring it into the app (Andy)

1. **Create the table:** apply `web/tickets/tickets.sql` to Neon, or append it to `db/schema.sql`.
2. **Add the routes:** in `app/src/handler.js`, at the top of `handle()`:
   ```js
   import { handleTickets, sqlTicketStore } from "../../web/tickets/tickets.js";
   // inside handle(), before the board/API routes:
   const t = await handleTickets(request, env, sqlTicketStore(db.query)); if (t) return t;
   ```
   Use whatever `query(text, params) -> rows` function `db.js` already builds.
3. **Link it from the live board,** or from the landing page, as "Request a recovery".

## Automatic quote email (the Recovery Manager writes and sends it)

```
customer submits /tickets
  -> app stores the ticket (status "new")
  -> app starts a Recovery Manager session on Naive with the ticket as data   (status "in_progress")
  -> Recovery Manager follows section T of its skill: writes a tailored email
     (what we understood, how we'd handle it for their kind of loss, the four-label promise,
      the price from Nash's quote.py / pricing.json, getting-started steps, reply APPROVE + files)
  -> agentmail.send_message from codecare-recover@agentmail.to to the ticket's email only
     (Nash: a consented ticket address counts as the client's thread; send-once per ticket_id)
  -> client replies on that thread with files -> Anna's intake bridge -> section A opens the case
```

The Recovery Manager is the only agent that can send client email; the Mail Scout only reads mail.
Section T is a **proposal for Anna's skill**: `web/tickets/recovery-manager-section-T.md`.

Switch it on in the app that serves the form (all three are needed; any missing = off):

| Setting | Value |
|---|---|
| `TICKETS_AUTOSTART` | `1` |
| `NAIVE_API_KEY` | a **narrow** Naive key (sessions:write only), as an app secret; never an admin key |
| `RECOVERY_MANAGER_AGENT_ID` | `agt_hy7jf2c1n0asqa3wrfna3742yb` |
| `TICKETS_MAX_SESSIONS_PER_DAY` | optional, default `20`: stops spam from spending credits |

and `npm i @usenaive-sdk/managed-agents` in that app (`web/tickets/naive.js` uses it exactly as the Naive
docs show). If Naive fails or the cap is hit, the customer still gets their reference and the ticket
stays `new` for a person.

Still to fill in: the "getting started" steps per environment (table in section T); until a row is
filled in, the email leaves that part out rather than inventing steps.
