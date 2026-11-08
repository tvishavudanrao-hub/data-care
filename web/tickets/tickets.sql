-- Ticket intake table. Separate file so db/schema.sql (Andrei's) is untouched until he merges it in.
-- Apply to the Neon dev branch with the app's schema script, or: psql "$NEON_DATABASE_URL" -f web/tickets/tickets.sql
create table if not exists tickets (
  ticket_id   text primary key,                       -- T-YYYYMMDD-XXXXX
  status      text not null default 'new' check (status in ('new','quoted','in_progress','closed')),
  name        text not null,
  email       text not null,
  company     text not null default '',
  kind        text not null check (kind in ('excel','code','other')),
  environment text not null default '',               -- where they use it, for the right install steps
  description text not null,
  consent     boolean not null,                       -- agreed to be emailed about this request
  quote_usd   numeric(10,2),
  case_id     text,                                   -- set when the Recovery Manager opens a case
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists tickets_status_created on tickets (status, created_at desc);
