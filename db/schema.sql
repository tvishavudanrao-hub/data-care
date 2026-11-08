-- Data Care records store (Neon). Schema from the "Code Care: full build spec v2" board post, section 5.
-- Agents never connect to this database: they write through the Data Care app's records API (naive/lib/cc.py).

create table cases (
  case_id text primary key,
  client_email text not null,
  kind text not null check (kind in ('excel','code','checkup','other')),
  stage text not null default 'intake',  -- intake, forensics, context, reconstruction, waiting_client, validation, approval, delivered, unresolved
  retry_count int not null default 0,
  quote_usd numeric(10,2),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create table fragments (
  fragment_id text primary key,
  case_id text not null references cases,
  source_file text not null,
  location text,
  type text not null check (type in ('code','record','clue')),
  confidence numeric(3,2),
  notes text,
  created_by text not null
);
create table rules (
  rule_id text primary key,
  case_id text not null references cases,
  description text not null,
  evidence text[] not null,
  alternatives jsonb not null default '[]',
  status text not null check (status in ('reconstructed and tested','reconstructed but untested','unresolved'))
);
create table gaps (
  gap_id text primary key,
  case_id text not null references cases,
  what text not null,
  why text,
  where_to_look text[],
  status text not null default 'open' check (status in ('open','found','requested','unresolved'))
);
create table verdicts (
  verdict_id bigserial primary key,
  case_id text not null references cases,
  pass boolean not null,
  results jsonb not null,  -- [{example_id, expected, actual}]
  retry_count int not null,
  created_at timestamptz not null default now()
);
create table report_items (
  item_id bigserial primary key,
  case_id text not null references cases,
  item text not null,
  label text not null check (label in ('recovered','reconstructed and tested','reconstructed but untested','unresolved')),
  cites text[] not null
);
create table events (
  event_id bigserial primary key,
  case_id text references cases,
  agent text not null,
  stage text not null,
  message text,
  cost_usd numeric(10,4) not null default 0,
  human_stepped_in boolean not null default false,
  created_at timestamptz not null default now()
);
create table checkups (
  checkup_id bigserial primary key,
  case_id text references cases,
  team text,
  repo_url text,
  high int not null default 0,
  medium int not null default 0,
  low int not null default 0,
  created_at timestamptz not null default now()
);
