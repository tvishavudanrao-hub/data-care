// Storage providers for the connectors. Each one is read-only and has the same shape:
//   name, label, authUrl(state), exchange(code) -> {refresh, access, account},
//   accessToken(refresh) -> access, search(access, terms) -> [file], download(access, file) -> {bytes,name,contentType},
//   revoke(refresh) -> {manual?: url}   (manual = the provider has no revoke API; we still delete our copy)
// A file is { id, name, mimeType, size, ...provider fields }.

const enc = (o) => new URLSearchParams(o);
const form = { "content-type": "application/x-www-form-urlencoded" };

export const WANTED_EXT = [".xlsx", ".xlsm", ".xls", ".csv", ".pdf", ".docx", ".txt", ".eml", ".msg", ".json",
  ".yml", ".yaml", ".py", ".js", ".ts", ".sql"];
const MIME_BY_EXT = { ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
  ".xls": "application/vnd.ms-excel", ".csv": "text/csv", ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".txt": "text/plain",
  ".eml": "message/rfc822", ".json": "application/json", ".yml": "application/x-yaml", ".yaml": "application/x-yaml",
  ".py": "text/x-python", ".js": "text/javascript", ".ts": "text/plain", ".sql": "text/plain", ".msg": "application/vnd.ms-outlook" };
const ext = (name) => { const m = String(name).toLowerCase().match(/\.[a-z0-9]+$/); return m ? m[0] : ""; };
export const wanted = (name) => WANTED_EXT.includes(ext(name));
export const mimeFor = (name) => MIME_BY_EXT[ext(name)] || "application/octet-stream";

export function emailFromIdToken(idToken) {
  try {
    const part = String(idToken).split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const c = JSON.parse(atob(part + "===".slice((part.length + 3) % 4)));
    return c.email || c.preferred_username || "";
  } catch { return ""; }
}

async function ok(r, what) {
  if (!r.ok) throw new Error(`${what} failed (${r.status})`);
  return r;
}
const dedupe = (files) => [...new Map(files.map((f) => [f.id, f])).values()];

// ---------------------------------------------------------------- Google Drive

const DRIVE = "https://www.googleapis.com/drive/v3";
export const GOOGLE_SCOPES = ["https://www.googleapis.com/auth/drive.readonly", "openid", "email"];
const G_EXPORTS = {
  "application/vnd.google-apps.spreadsheet": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"],
  "application/vnd.google-apps.document": ["application/pdf", ".pdf"],
};
const G_MIME = ["application/vnd.google-apps.spreadsheet", "application/vnd.google-apps.document",
  ...new Set(Object.values(MIME_BY_EXT))];

export function googleDrive(env, fetchImpl = fetch) {
  const redirect = env.PUBLIC_BASE_URL + "/connect/google/callback";
  const q = (s) => s.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  return {
    name: "google_drive", slug: "google", label: "Google Drive",
    authUrl: (state) => "https://accounts.google.com/o/oauth2/v2/auth?" + enc({ client_id: env.GOOGLE_CLIENT_ID, redirect_uri: redirect,
      response_type: "code", scope: GOOGLE_SCOPES.join(" "), access_type: "offline", prompt: "consent", include_granted_scopes: "false", state }),
    async exchange(code) {
      const r = await ok(await fetchImpl("https://oauth2.googleapis.com/token", { method: "POST", headers: form, body: enc({ code,
        client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, redirect_uri: redirect, grant_type: "authorization_code" }) }), "Google sign-in");
      const t = await r.json();
      if (!String(t.scope || "").includes("drive.readonly")) throw new Error("read-only Drive access was not granted");
      return { refresh: t.refresh_token, access: t.access_token, account: emailFromIdToken(t.id_token) };
    },
    async accessToken(refresh) {
      const r = await ok(await fetchImpl("https://oauth2.googleapis.com/token", { method: "POST", headers: form, body: enc({
        refresh_token: refresh, client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, grant_type: "refresh_token" }) }), "Google refresh");
      return (await r.json()).access_token;
    },
    async search(access, terms) {
      const text = terms.map((t) => `name contains '${q(t)}' or fullText contains '${q(t)}'`).join(" or ");
      const mimes = G_MIME.map((m) => `mimeType = '${m}'`).join(" or ");
      const p = enc({ q: `trashed = false and (${mimes}) and (${text})`, pageSize: "100", orderBy: "modifiedTime desc",
        fields: "files(id,name,mimeType,size,modifiedTime)", supportsAllDrives: "true", includeItemsFromAllDrives: "true" });
      const r = await ok(await fetchImpl(`${DRIVE}/files?${p}`, { headers: { authorization: `Bearer ${access}` } }), "Drive search");
      return (await r.json()).files || [];
    },
    async download(access, f) {
      const ex = G_EXPORTS[f.mimeType];
      const url = ex ? `${DRIVE}/files/${encodeURIComponent(f.id)}/export?mimeType=${encodeURIComponent(ex[0])}`
        : `${DRIVE}/files/${encodeURIComponent(f.id)}?alt=media&supportsAllDrives=true`;
      const r = await ok(await fetchImpl(url, { headers: { authorization: `Bearer ${access}` } }), "download");
      const name = ex && !f.name.toLowerCase().endsWith(ex[1]) ? f.name + ex[1] : f.name;
      return { bytes: new Uint8Array(await r.arrayBuffer()), name, contentType: ex ? ex[0] : f.mimeType };
    },
    async revoke(refresh) {
      await fetchImpl("https://oauth2.googleapis.com/revoke", { method: "POST", headers: form, body: enc({ token: refresh }) });
      return {};
    },
  };
}

// ---------------------------------------------------------------- Microsoft 365 (OneDrive / SharePoint)

const GRAPH = "https://graph.microsoft.com/v1.0";
export const MICROSOFT_SCOPES = ["offline_access", "openid", "email", "User.Read", "Files.Read.All"];

export function microsoft365(env, fetchImpl = fetch) {
  const tenant = env.MICROSOFT_TENANT || "common";
  const base = `https://login.microsoftonline.com/${tenant}/oauth2/v2.0`;
  const redirect = env.PUBLIC_BASE_URL + "/connect/microsoft/callback";
  return {
    name: "microsoft_365", slug: "microsoft", label: "Microsoft 365 / OneDrive",
    authUrl: (state) => `${base}/authorize?` + enc({ client_id: env.MICROSOFT_CLIENT_ID, response_type: "code", redirect_uri: redirect,
      response_mode: "query", scope: MICROSOFT_SCOPES.join(" "), prompt: "consent", state }),
    async exchange(code) {
      const r = await ok(await fetchImpl(`${base}/token`, { method: "POST", headers: form, body: enc({ client_id: env.MICROSOFT_CLIENT_ID,
        client_secret: env.MICROSOFT_CLIENT_SECRET, code, redirect_uri: redirect, grant_type: "authorization_code",
        scope: MICROSOFT_SCOPES.join(" ") }) }), "Microsoft sign-in");
      const t = await r.json();
      const granted = String(t.scope || "").toLowerCase();
      if (!granted.includes("files.read")) throw new Error("read access to files was not granted");
      if (/files\.readwrite/.test(granted)) throw new Error("refusing a token with write access; we only accept read-only");
      return { refresh: t.refresh_token, access: t.access_token, account: emailFromIdToken(t.id_token) };
    },
    async accessToken(refresh) {
      const r = await ok(await fetchImpl(`${base}/token`, { method: "POST", headers: form, body: enc({ client_id: env.MICROSOFT_CLIENT_ID,
        client_secret: env.MICROSOFT_CLIENT_SECRET, refresh_token: refresh, grant_type: "refresh_token",
        scope: MICROSOFT_SCOPES.join(" ") }) }), "Microsoft refresh");
      return (await r.json()).access_token;
    },
    async search(access, terms) {
      const out = [];
      for (const t of terms.slice(0, 8)) { // one query per word, so each result knows why it matched
        const r = await ok(await fetchImpl(`${GRAPH}/me/drive/root/search(q='${encodeURIComponent(t.replace(/'/g, "''"))}')` +
          "?$top=50&$select=id,name,size,file,parentReference", { headers: { authorization: `Bearer ${access}` } }), "OneDrive search");
        for (const it of (await r.json()).value || []) {
          if (!it.file || !wanted(it.name)) continue; // folders and unrelated types are never copied
          out.push({ id: it.id, name: it.name, size: String(it.size ?? ""), mimeType: it.file.mimeType || mimeFor(it.name),
            driveId: it.parentReference && it.parentReference.driveId });
        }
      }
      return dedupe(out);
    },
    async download(access, f) {
      const path = f.driveId ? `/drives/${encodeURIComponent(f.driveId)}/items/${encodeURIComponent(f.id)}/content`
        : `/me/drive/items/${encodeURIComponent(f.id)}/content`;
      const r = await ok(await fetchImpl(GRAPH + path, { headers: { authorization: `Bearer ${access}` } }), "download");
      return { bytes: new Uint8Array(await r.arrayBuffer()), name: f.name, contentType: f.mimeType };
    },
    // Microsoft has no per-app token revoke API. We delete our copy; the client can remove the app here:
    async revoke() { return { manual: "https://myapps.microsoft.com" }; },
  };
}

// ---------------------------------------------------------------- Dropbox

export const DROPBOX_SCOPES = ["account_info.read", "files.metadata.read", "files.content.read"];

export function dropbox(env, fetchImpl = fetch) {
  const redirect = env.PUBLIC_BASE_URL + "/connect/dropbox/callback";
  const api = "https://api.dropboxapi.com";
  const self = {
    name: "dropbox", slug: "dropbox", label: "Dropbox",
    authUrl: (state) => "https://www.dropbox.com/oauth2/authorize?" + enc({ client_id: env.DROPBOX_APP_KEY, response_type: "code",
      redirect_uri: redirect, token_access_type: "offline", scope: DROPBOX_SCOPES.join(" "), state }),
    async exchange(code) {
      const r = await ok(await fetchImpl(`${api}/oauth2/token`, { method: "POST", headers: form, body: enc({ code, grant_type: "authorization_code",
        client_id: env.DROPBOX_APP_KEY, client_secret: env.DROPBOX_APP_SECRET, redirect_uri: redirect }) }), "Dropbox sign-in");
      const t = await r.json();
      const granted = String(t.scope || "");
      if (!granted.includes("files.content.read")) throw new Error("read access to files was not granted");
      if (/files\.content\.write|files\.permanent_delete/.test(granted)) throw new Error("refusing a token with write access");
      let account = "";
      try {
        const a = await fetchImpl(`${api}/2/users/get_current_account`, { method: "POST", headers: { authorization: `Bearer ${t.access_token}` } });
        if (a.ok) account = (await a.json()).email || "";
      } catch { /* the email is only shown back to the client */ }
      return { refresh: t.refresh_token, access: t.access_token, account };
    },
    async accessToken(refresh) {
      const r = await ok(await fetchImpl(`${api}/oauth2/token`, { method: "POST", headers: form, body: enc({ grant_type: "refresh_token",
        refresh_token: refresh, client_id: env.DROPBOX_APP_KEY, client_secret: env.DROPBOX_APP_SECRET }) }), "Dropbox refresh");
      return (await r.json()).access_token;
    },
    async search(access, terms) {
      const out = [];
      for (const t of terms.slice(0, 8)) {
        const r = await ok(await fetchImpl(`${api}/2/files/search_v2`, { method: "POST",
          headers: { authorization: `Bearer ${access}`, "content-type": "application/json" },
          body: JSON.stringify({ query: t, options: { max_results: 50, file_status: "active" } }) }), "Dropbox search");
        for (const m of (await r.json()).matches || []) {
          const md = m.metadata && m.metadata.metadata;
          if (!md || md[".tag"] !== "file" || !wanted(md.name)) continue;
          out.push({ id: md.id, name: md.name, size: String(md.size ?? ""), mimeType: mimeFor(md.name), path: md.path_lower });
        }
      }
      return dedupe(out);
    },
    async download(access, f) {
      const r = await ok(await fetchImpl("https://content.dropboxapi.com/2/files/download", { method: "POST",
        headers: { authorization: `Bearer ${access}`, "Dropbox-API-Arg": JSON.stringify({ path: f.id }) } }), "download");
      return { bytes: new Uint8Array(await r.arrayBuffer()), name: f.name, contentType: f.mimeType };
    },
    async revoke(refresh) {
      const access = await self.accessToken(refresh); // Dropbox revokes by access token; that ends the whole grant
      await fetchImpl(`${api}/2/auth/token/revoke`, { method: "POST", headers: { authorization: `Bearer ${access}` } });
      return {};
    },
  };
  return self;
}

// ---------------------------------------------------------------- GitHub (GitHub App, Contents: read-only)
// A classic OAuth app can only get read AND write to private repos ("repo" scope), which would break our
// read-only promise. A GitHub App with repository permission "Contents: Read-only" (and "Metadata: Read")
// gives user tokens that can only read the repos where the client installed the app.

export function github(env, fetchImpl = fetch) {
  const redirect = env.PUBLIC_BASE_URL + "/connect/github/callback";
  const gh = { accept: "application/vnd.github+json", "x-github-api-version": "2022-11-28" };
  return {
    name: "github", slug: "github", label: "GitHub",
    authUrl: (state) => "https://github.com/login/oauth/authorize?" + enc({ client_id: env.GITHUB_CLIENT_ID, redirect_uri: redirect, state }),
    async exchange(code) {
      const r = await ok(await fetchImpl("https://github.com/login/oauth/access_token", { method: "POST",
        headers: { ...form, accept: "application/json" }, body: enc({ client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET, code, redirect_uri: redirect }) }), "GitHub sign-in");
      const t = await r.json();
      if (t.error) throw new Error(`GitHub sign-in failed (${t.error})`);
      let account = "";
      try {
        const u = await fetchImpl("https://api.github.com/user", { headers: { ...gh, authorization: `Bearer ${t.access_token}` } });
        if (u.ok) account = (await u.json()).login || "";
      } catch { /* shown back to the client only */ }
      // GitHub Apps with expiring tokens return a refresh token; otherwise keep the user token itself.
      return { refresh: t.refresh_token || t.access_token, access: t.access_token, account: account ? `github:${account}` : "" };
    },
    async accessToken(refresh) {
      if (!refresh.startsWith("ghr_")) return refresh; // non-expiring user token
      const r = await ok(await fetchImpl("https://github.com/login/oauth/access_token", { method: "POST",
        headers: { ...form, accept: "application/json" }, body: enc({ client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET, grant_type: "refresh_token", refresh_token: refresh }) }), "GitHub refresh");
      return (await r.json()).access_token;
    },
    async search(access, terms) {
      const auth = { ...gh, authorization: `Bearer ${access}` };
      const repos = await (await ok(await fetchImpl("https://api.github.com/user/installations?per_page=20", { headers: auth }), "GitHub installations")).json();
      const out = [];
      for (const inst of (repos.installations || []).slice(0, 5)) {
        const rl = await (await ok(await fetchImpl(`https://api.github.com/user/installations/${inst.id}/repositories?per_page=50`,
          { headers: auth }), "GitHub repositories")).json();
        for (const repo of (rl.repositories || []).slice(0, 20)) {
          const tree = await fetchImpl(`https://api.github.com/repos/${repo.full_name}/git/trees/${encodeURIComponent(repo.default_branch)}?recursive=1`,
            { headers: auth });
          if (!tree.ok) continue;
          for (const it of (await tree.json()).tree || []) {
            if (it.type !== "blob" || !wanted(it.path)) continue;
            const lower = it.path.toLowerCase();
            if (!terms.some((t) => lower.includes(t))) continue; // only paths that match the case's words
            out.push({ id: `${repo.full_name}:${it.path}`, name: `${repo.full_name}/${it.path}`, size: String(it.size ?? ""),
              mimeType: mimeFor(it.path), repo: repo.full_name, path: it.path, ref: repo.default_branch });
          }
        }
      }
      return dedupe(out);
    },
    async download(access, f) {
      const r = await ok(await fetchImpl(`https://api.github.com/repos/${f.repo}/contents/${f.path.split("/").map(encodeURIComponent).join("/")}` +
        `?ref=${encodeURIComponent(f.ref)}`, { headers: { ...gh, accept: "application/vnd.github.raw", authorization: `Bearer ${access}` } }), "download");
      return { bytes: new Uint8Array(await r.arrayBuffer()), name: f.name.replace(/\//g, "__"), contentType: f.mimeType };
    },
    async revoke(refresh) {
      const access = await this.accessToken(refresh);
      await fetchImpl(`https://api.github.com/applications/${env.GITHUB_CLIENT_ID}/grant`, { method: "DELETE",
        headers: { ...gh, authorization: "Basic " + btoa(`${env.GITHUB_CLIENT_ID}:${env.GITHUB_CLIENT_SECRET}`), "content-type": "application/json" },
        body: JSON.stringify({ access_token: access }) });
      return {};
    },
  };
}

// ---------------------------------------------------------------- registry

export const PROVIDER_SLUGS = ["google", "microsoft", "dropbox", "github"];

/** Providers switched on by their settings. Missing settings = shown as "coming soon". */
export function providers(env, fetchImpl = fetch) {
  const all = {
    google: env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET ? googleDrive(env, fetchImpl) : null,
    microsoft: env.MICROSOFT_CLIENT_ID && env.MICROSOFT_CLIENT_SECRET ? microsoft365(env, fetchImpl) : null,
    dropbox: env.DROPBOX_APP_KEY && env.DROPBOX_APP_SECRET ? dropbox(env, fetchImpl) : null,
    github: env.GITHUB_CLIENT_ID && env.GITHUB_CLIENT_SECRET ? github(env, fetchImpl) : null,
  };
  return Object.fromEntries(Object.entries(all).filter(([, p]) => p));
}

export const LABELS = { google: "Google Drive", microsoft: "Microsoft 365 / OneDrive", dropbox: "Dropbox", github: "GitHub" };
