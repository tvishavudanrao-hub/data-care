# Connectors: we find the evidence, the client doesn't upload it

This lets a client **connect their own storage, read-only**. The site then searches it for the evidence a recovery needs: older copies, exports, reports and related files. No attachments, no size limits from email, and no guessing which file matters.

Connectors: **Google Drive, Microsoft 365 (OneDrive and SharePoint), Dropbox and GitHub**. All of them are read-only, and each is switched on by its own settings; one without settings shows as "coming soon". The client can connect several, and each is searched and logged separately.

## Flow

```
/tickets  ->  ticket gets a personal connect link  ->  RM's quote email includes it (section T)
client opens /connect/<link>: trust promises, "Connect Google Drive (read-only)"
  -> Google consent (scope drive.readonly)  ->  /connect/google/callback
  -> token stored AES-GCM encrypted; ticket status "approved"
  -> search Drive with words from the ticket + kind (only spreadsheets, CSV, PDF, docs, mail, code)
  -> copy matches into the Naive file library folder <ticket_id>-incoming (caps: 40 files,
     100 MB each, 300 MB total); every file seen is logged
  -> start the Recovery Manager: "WEBSITE TICKET APPROVED" (section T2) -> case opens -> Forensics scans first
client sees /connect/<link>/status: every file, copied or not and why; "Disconnect now"
POST /api/connectors/revoke-expired (cron, x-cc-token): auto-revoke after CONNECTOR_MAX_DAYS (default 14)
```

**It runs in the website app, not in a Naive agent.** The client's token is a secret, and Naive can't pass secrets into agent sandboxes yet. The agents only ever see copied files, which Forensics scans first.

## Trust, enforced in code (each one tested)

- **Read-only Drive only.** If the client unticks read-only Drive on Google's screen, nothing is stored or read.
- **Forgery-proof links.** The OAuth `state` is signed, so a tampered callback is rejected before anything is read.
- **Matching files only.** Only files that match the case are copied, within count and size caps. Skipped files are logged with the reason.
- **Tokens protected.** Tokens are encrypted at rest, revoked at Google on disconnect or expiry, and wiped from our database.
- **Files never opened here.** They're stored, never opened or run.
- **Client text escaped.** Everything the client typed is escaped on every page. File names and ticket text go to the agents marked as data.

## Switch it on (Andy, plus whoever owns each developer account)

**1. Register an app with each provider you want.** The redirect URI is always `https://<site>/connect/<provider>/callback`.

| Provider | Where | Read-only access to request | Settings it gives you |
|---|---|---|---|
| **Google Drive** | Google Cloud console: enable the Drive API, set up the OAuth consent screen, create a web OAuth client | `drive.readonly`, `openid`, `email` | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| **Microsoft 365** | Microsoft Entra admin center, App registrations (accounts in any org plus personal) | Delegated `Files.Read.All`, `User.Read`, `offline_access`, `openid`, `email` | `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, optional `MICROSOFT_TENANT` (default `common`) |
| **Dropbox** | Dropbox App Console: Scoped access, Full Dropbox | `account_info.read`, `files.metadata.read`, `files.content.read` (tick nothing else) | `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` |
| **GitHub** | GitHub Settings, Developer settings, **GitHub Apps** (not OAuth Apps), with "Expire user tokens" on | Repository permissions: **Contents: Read-only**, Metadata: Read-only. No write permissions. | `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` |

Notes:
- **Google:** `drive.readonly` is a restricted scope, so a public launch needs Google's verification. In "Testing" mode only listed test users can connect.
- **GitHub:** a classic OAuth App can only get read *and write* access to private repos, which would break the read-only promise. Use a GitHub App. The client must also **install** it on the repos they want searched, and we only see those.
- **Microsoft:** there is no API for an app to cancel its own access. On disconnect we delete our token, and the status page links the client to myapps.microsoft.com to remove us.
- **Write access is refused.** If a Microsoft or Dropbox token ever comes back with write access, we refuse it and read nothing.

**2. App secrets** (Vercel, never in the repo). Add the provider settings above, plus:

| Setting | Value |
|---|---|
| `PUBLIC_BASE_URL` | e.g. `https://datacare-71m10sqe9a2n.vercel.app` |
| `CONNECTOR_KEY` | 32 random bytes, base64: `openssl rand -base64 32` |
| `NAIVE_FILES_API_KEY` | a Naive key with **files:write only** |
| `CONNECTOR_MAX_DAYS` | optional, default `14` |

**3. Database:** apply `web/tickets/tickets.sql`, then `web/connectors/connectors.sql`, to Neon.

**4. Wiring:** in `app/src/handler.js`, before the other routes:
   ```js
   import { handleConnectors, sqlConnectorStore } from "../../web/connectors/connectors.js";
   import { naiveFiles } from "../../web/connectors/naive_files.js";
   import { naiveSessionStarter } from "../../web/tickets/naive.js";
   const c = await handleConnectors(request, env, { store: sqlConnectorStore(query), files: naiveFiles(env),
     startSession: env.TICKETS_AUTOSTART === "1" ? naiveSessionStarter(env) : null });
   if (c) return c;
   ```
   Then `npm i @usenaive-sdk/managed-agents` in `app/`. The app's ticket copy in `app/src/tickets/` also needs the `connect_token` change from `web/tickets/tickets.js`.

**5. Recovery Manager:** Anna adds `recovery-manager-section-T2.md` to the skill. It already says "Google Drive"; read that as "the connected storage" (the message names the `source`).

**6. Cron:** call `POST /api/connectors/revoke-expired` daily, for example with a Vercel cron.

## Try it locally (pretend Drive, nothing leaves your machine)

```bash
node web/connectors/server.js
```

1. Open http://127.0.0.1:8791/tickets and submit.
4. On the connect page, every provider is clickable, each with its own pretend storage. Connect several, then open the status page.
2. Open the connect link printed in the terminal, then click Connect.
3. The terminal shows what would be copied and the message the Recovery Manager would receive.

```bash
cd web/connectors && npm test
```

There are 14 tests, including the real SQL on Postgres via PGlite.

## Known limits (honest)

- **Naive upload is unverified.** `naive_files.js` uses the documented `files.upload(FormData)`. Its `folder` field mirrors the CLI's `--folder` flag, but it hasn't been tried against Naive yet. Do one real upload and check it with `naive file list --folder <ticket>-incoming`.
- **Search runs in the callback.** That's fine for the caps above, but Vercel functions have a time limit. For big Drives, move the search to a background job.
- **GitHub reads only current files.** It reads the default branch, so a deleted module is only found if a copy or its tests survive there. Searching git history is a later step.
- **Providers tested against fakes.** All four are tested with fake versions that answer like the real APIs. None has been tried with a real account yet; each needs its developer app registered first.
- **Desktop scout not built.** For files only on a laptop, a desktop scout app is the later step. Context's scanner can already take a whole-computer export.
