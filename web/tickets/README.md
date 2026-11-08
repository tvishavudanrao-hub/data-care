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

## How we get back to the customer (proposal)

1. **The Recovery Manager**, or a person, lists `GET /api/tickets?status=new`.
2. **It opens a case:** `cc.py case-new --case C-00NN --client-email <email> --kind <kind>`.
3. **It patches the ticket** with `{"case_id": "C-00NN"}`.
4. **It drafts the reply** from the `codecare-recover` inbox. The reply covers:
   - the quote
   - install steps for the customer's `environment`
   - how to share files safely

   It's sent only after a person approves (AgentMail send stays on "ask").
5. **It patches the ticket** with `{"status": "quoted", "quote_usd": N}`.
6. **When the customer replies with files,** Anna's intake bridge picks them up as usual and the pipeline runs.

**Not built yet:**
- the reply email template
- the install steps for each environment, which depend on what we ship
- a rate limit per IP
