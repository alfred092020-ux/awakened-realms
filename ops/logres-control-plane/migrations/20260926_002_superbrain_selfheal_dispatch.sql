create table if not exists brain_reconciliation_actions(
  id integer primary key autoincrement,
  run_id text,
  entity_kind text not null,
  entity_id text not null,
  action text not null,
  before_state text,
  after_state text,
  reason text not null,
  created_at text not null,
  metadata_json text not null default '{}'
);
create index if not exists brain_reconciliation_actions_entity_idx
  on brain_reconciliation_actions(entity_kind,entity_id,id);

create table if not exists brain_wake_dispatch_receipts(
  id integer primary key autoincrement,
  wake_id integer not null,
  attempt integer not null,
  dispatcher text not null,
  transport text not null,
  cost_class text not null default 'unknown',
  status text not null,
  started_at text not null,
  finished_at text,
  error text,
  metadata_json text not null default '{}'
);
create index if not exists brain_wake_dispatch_receipts_wake_idx
  on brain_wake_dispatch_receipts(wake_id,attempt,id);
create index if not exists brain_wake_queue_claim_idx
  on brain_wake_queue(state,claimed_at,id);
