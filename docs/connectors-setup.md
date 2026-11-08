# Switching on the storage connectors

The code is built, tested and deployed. Each provider stays "coming soon" on the connect page until its keys are set. This page is the click-by-click setup. The site is `https://datacare-71m10sqe9a2n.vercel.app` below; use the real URL if it changes.

Never paste a secret into the repo, the board or a chat. Secrets go straight into the app's settings on Vercel.

Order: Microsoft first (the demo showcase), then Google. Dropbox and GitHub are optional.

## 1. Microsoft 365 / OneDrive / SharePoint (~10 min, any Microsoft account)

1. Go to https://entra.microsoft.com → **Identity → Applications → App registrations → New registration**. (A personal Microsoft account works; it gets a default directory.)
2. Fill in:
   - **Name:** `Data Care`
   - **Supported account types:** *Accounts in any organizational directory and personal Microsoft accounts*
   - **Redirect URI:** platform **Web**, value `https://datacare-71m10sqe9a2n.vercel.app/connect/microsoft/callback`
3. Click **Register**. Copy the **Application (client) ID**; that's `MICROSOFT_CLIENT_ID`.
4. **Certificates & secrets → Client secrets → New client secret.** Copy the **Value** (not the Secret ID) at once; it's shown only once. That's `MICROSOFT_CLIENT_SECRET`.
5. **API permissions → Add a permission → Microsoft Graph → Delegated permissions.** Tick `Files.Read.All`, `User.Read`, `offline_access`, `openid` and `email`, then **Add permissions**. Add nothing with "Write" or "ReadWrite" in the name: the app refuses write tokens anyway.
6. Leave `MICROSOFT_TENANT` unset (it defaults to `common`, so work and personal accounts both work).

Note: some company tenants block users from consenting to outside apps. If a client sees "Need admin approval", their IT admin must approve Data Care once. Personal accounts and most small-business tenants are fine.

## 2. Google Drive (~10 min, a Google account)

1. Go to https://console.cloud.google.com → create a project named `Data Care`.
2. **APIs & Services → Library →** search for **Google Drive API → Enable**.
3. **APIs & Services → OAuth consent screen** (Google Auth Platform):
   - **User type:** External
   - **App name:** `Data Care`, with your support email
   - **Scopes:** add `.../auth/drive.readonly`, `openid` and `email`
   - **Audience → Test users:** add every Google account that will connect during the demo, including your own
4. **Credentials → Create credentials → OAuth client ID:**
   - **Type:** Web application
   - **Authorized redirect URI:** `https://datacare-71m10sqe9a2n.vercel.app/connect/google/callback`
5. Copy the **Client ID** and **Client secret** into `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

Note: `drive.readonly` is a restricted scope. While the app is in Testing, only the listed test users can connect, and Google shows an "unverified app" warning (click **Continue**). A public launch needs Google's verification.

## 3. Dropbox (optional, ~5 min)

1. Go to https://www.dropbox.com/developers/apps → **Create app**. Choose **Scoped access**, **Full Dropbox** and the name `Data Care`.
2. **Permissions** tab: tick only `account_info.read`, `files.metadata.read` and `files.content.read`, then **Submit**.
3. **Settings** tab:
   - **Redirect URI:** `https://datacare-71m10sqe9a2n.vercel.app/connect/dropbox/callback`
   - Copy the **App key** and **App secret** into `DROPBOX_APP_KEY` and `DROPBOX_APP_SECRET`.
4. In development mode, only accounts you add under **Development users** (up to 500) can connect.

## 4. GitHub (optional, ~5 min)

Use a **GitHub App**, not an OAuth App: an OAuth App can't be read-only on private repos.

1. Go to GitHub **Settings → Developer settings → GitHub Apps → New GitHub App**.
   - **Callback URL:** `https://datacare-71m10sqe9a2n.vercel.app/connect/github/callback`
   - Tick **Expire user authorization tokens**.
   - **Webhook:** untick Active.
   - **Repository permissions:** **Contents: Read-only**, Metadata: Read-only. Nothing else.
   - **Where can it be installed:** Any account.
2. Create it, then copy the **Client ID** and generate a **client secret** into `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`.

## 5. App settings and redeploy (Andrei)

Vercel → the Data Care project → **Settings → Environment Variables** (Production):

| Setting | Value |
|---|---|
| `PUBLIC_BASE_URL` | `https://datacare-71m10sqe9a2n.vercel.app` (no trailing slash) |
| `CONNECTOR_KEY` | output of `openssl rand -base64 32` (generate it once; changing it later makes stored tokens unreadable) |
| `NAIVE_FILES_API_KEY` | a Naive API key with **files:write only** |
| `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET` | from step 1 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | from step 2 |
| `DROPBOX_APP_KEY`, `DROPBOX_APP_SECRET` | from step 3 (optional) |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | from step 4 (optional) |

Then:

```bash
cd app && npm run connectors-table
```

Redeploy. If the connectors table already exists, `npm run connectors-table` changes nothing.

Make sure `TICKETS_AUTOSTART=1`, `NAIVE_API_KEY` and `RECOVERY_MANAGER_AGENT_ID` are still set, so connecting starts the Recovery Manager.

## 6. Recovery Manager wording (Anna)

Add `web/connectors/recovery-manager-section-T2.md` to the front-desk-and-coordinator skill. It has two parts:
- the `connect_url` sentence in the quote email
- the new section T2

Push the skill version, update the Recovery Manager to it, and re-save the roster.

## 7. Test it (~5 min)

1. Submit a ticket on `/tickets` with your own email.
2. Check that the quote email has a `/connect/<token>` link. Open it; Microsoft (and Google) should be clickable.
3. Connect your own OneDrive with a test spreadsheet whose name matches words in your ticket.
4. The status page should list the file as "copied for your case".
5. Check that it landed in Naive (this is the one unverified piece):

   ```bash
   naive file list --folder <ticket_id>-incoming
   ```

6. Check that a Recovery Manager session started with "WEBSITE TICKET APPROVED":

   ```bash
   naive session list
   ```

7. Press **Disconnect now**; the status page should say access has ended.

If step 5 shows the file outside the folder, tell Tvisha's Claude: the fix is in `web/connectors/naive_files.js`.
