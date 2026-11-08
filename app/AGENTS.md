# Data Care app

Records API for the agents and the live Data Care board. Owner: Andrei (@andrei-jacques).

## Files
- `src/handler.js`: routes. Fetch-standard, so the same code runs as a Worker (`worker.js`) or under Node (`server.js`).
- `src/db.js`: every SQL statement, the allowed columns per table, the board query.
- `src/board.js`: the board page (HTML string), polls `GET /api/board` every 5 seconds.
- `src/neon.js`: Neon over HTTP (`@neondatabase/serverless`).
- `../db/schema.sql`: the Neon schema (v2 spec, section 5). `../naive/lib/cc.py`: the agents' client.

## Routes
| Route | Auth | What |
| --- | --- | --- |
| `POST /api/{cases,fragments,rules,gaps,verdicts,report_items,events,checkups}` | `x-cc-token` | Insert a row. Re-sending the same id (case, fragment, rule, gap) updates it, so retries are safe. |
| `PATCH /api/cases/<case_id>` | `x-cc-token` | `stage`, `retry_count`, `quote_usd`. |
| `GET /api/health` | none | `{ok, db, token_valid}`. `cc.py ping` calls it. |
| `GET /api/board`, `GET /` | none | Board data and page. Client emails are masked (`c***@acme.com`). |

Errors come back as `{"error": "..."}` with a 400 that says what to fix (unknown field, missing field, a label outside the four, a case that does not exist yet).

## Environment (app secrets, never in the repo)
- `NEON_DATABASE_URL`: the Neon `dev` branch connection string (pooled).
- `CC_API_TOKEN`: shared token the agents send as `x-cc-token`. Agents get it from the Naive vault as an env var bound to this app's host.

## Run and test locally
```bash
npm install
npm test                          # API tests on an in-memory Postgres (PGlite)
PORT=8787 CC_API_TOKEN=dev node server.js   # board at http://127.0.0.1:8787
python3 ../naive/lib/test_cc.py   # cc.py end to end against this server
```
Set `NEON_DATABASE_URL` in the environment to run against Neon instead of memory.

## Deploying on Naive
`naive app create datacare --type fullstack`, set the two secrets, then `naive app deploy <app-id> .`.
Not yet confirmed: which build the platform runs for a fullstack app. `worker.js` exports a standard
`fetch(request, env)` handler; if the platform expects another entry shape, only that file changes.
