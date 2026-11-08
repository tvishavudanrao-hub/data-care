-- Connector tables (apply after web/tickets/tickets.sql). Tokens are stored AES-GCM encrypted with
-- CONNECTOR_KEY and wiped on revoke; the access log is what the client sees on the status page.
alter table tickets add column if not exists connect_token text unique;
alter table tickets drop constraint if exists tickets_status_check;
alter table tickets add constraint tickets_status_check check (status in ('new','quoted','approved','in_progress','closed'));

create table if not exists connections (
  id             bigserial primary key,
  ticket_id      text not null references tickets (ticket_id),
  provider       text not null,                 -- google_drive (microsoft_365, dropbox, github later)
  sealed_refresh text not null,                 -- encrypted refresh token; '' after revoke
  account        text not null default '',      -- the account the client connected, shown back to them
  created_at     timestamptz not null default now(),
  revoked_at     timestamptz
);
create table if not exists connector_access (
  id            bigserial primary key,
  ticket_id     text not null references tickets (ticket_id),
  provider      text not null,
  external_id   text not null default '',      -- the file id in the client's storage
  name          text not null,
  mime          text not null default '',
  size_bytes    bigint,
  matched_terms text not null default '',
  action        text not null check (action in ('fetched','skipped')),
  reason        text not null default '',
  naive_file_id text,                           -- where the copy lives in the Naive file library
  at            timestamptz not null default now()
);
create index if not exists connector_access_ticket on connector_access (ticket_id, at);
