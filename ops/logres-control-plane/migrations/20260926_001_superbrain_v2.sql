create table if not exists brain_agent_sessions(
  session_key text primary key,
  member_id text not null,
  provider text not null,
  external_session_id text,
  session_kind text not null default 'agent',
  state text not null default 'UNKNOWN',
  cost_class text not null default 'unknown',
  capabilities_json text not null default '[]',
  wake_method text not null default 'brain_event',
  wake_target text,
  last_seen_epoch real not null default 0,
  last_synced_at text not null,
  metadata_json text not null default '{}',
  unique(provider, external_session_id)
);
create index if not exists brain_agent_sessions_member_idx
  on brain_agent_sessions(member_id,state,last_seen_epoch);
create index if not exists brain_agent_sessions_provider_idx
  on brain_agent_sessions(provider,state,last_seen_epoch);

create table if not exists brain_capabilities(
  member_id text not null,
  capability text not null,
  provider text not null default '',
  model text not null default '',
  cost_class text not null default 'unknown',
  cost_per_mtoken real,
  isolation_level text not null default 'unknown',
  max_concurrency integer not null default 1,
  health text not null default 'UNKNOWN',
  updated_at text not null,
  metadata_json text not null default '{}',
  primary key(member_id,capability,provider,model)
);
create index if not exists brain_capabilities_route_idx
  on brain_capabilities(capability,health,cost_class,isolation_level);

create table if not exists brain_event_subscriptions(
  subscription_id text primary key,
  subscriber text not null,
  event_type text not null default '*',
  priority_ceiling integer not null default 9,
  task_id text,
  wake_method text not null default 'brain_event',
  enabled integer not null default 1,
  created_at text not null,
  metadata_json text not null default '{}'
);
create index if not exists brain_event_subscriptions_subscriber_idx
  on brain_event_subscriptions(subscriber,enabled,event_type);

create table if not exists brain_wake_queue(
  id integer primary key autoincrement,
  subscription_id text not null,
  event_id integer not null,
  subscriber text not null,
  state text not null default 'PENDING',
  attempts integer not null default 0,
  available_epoch real not null default 0,
  claimed_by text,
  claimed_at text,
  last_error text,
  created_at text not null,
  updated_at text not null,
  unique(subscription_id,event_id)
);
create index if not exists brain_wake_queue_state_idx
  on brain_wake_queue(state,available_epoch,id);
create index if not exists brain_wake_queue_subscriber_idx
  on brain_wake_queue(subscriber,state,id);

create table if not exists brain_context_deliveries(
  delivery_id text primary key,
  task_id text not null,
  recipient text not null,
  pack_sha256 text not null,
  artifact_path text not null,
  status text not null default 'READY',
  created_at text not null,
  consumed_at text,
  metadata_json text not null default '{}'
);
create index if not exists brain_context_deliveries_task_idx
  on brain_context_deliveries(task_id,recipient,status,created_at);

create table if not exists evidence_assertions(
  assertion_id text primary key,
  subject text not null,
  predicate text not null,
  object_json text not null,
  provenance text not null default '',
  confidence real not null default 0.0,
  status text not null default 'ACTIVE',
  source_task_id text,
  source_event_id integer,
  supersedes_id text,
  retracted_at text,
  retraction_reason text,
  created_at text not null,
  updated_at text not null,
  metadata_json text not null default '{}'
);
create index if not exists evidence_assertions_subject_idx
  on evidence_assertions(subject,predicate,status,confidence);
create index if not exists evidence_assertions_task_idx
  on evidence_assertions(source_task_id,status);

create table if not exists brain_reconciliation_runs(
  run_id text primary key,
  started_at text not null,
  finished_at text,
  status text not null default 'RUNNING',
  checked_count integer not null default 0,
  finding_count integer not null default 0,
  metadata_json text not null default '{}'
);
create table if not exists brain_reconciliation_findings(
  id integer primary key autoincrement,
  run_id text not null,
  entity_kind text not null,
  entity_id text not null,
  severity text not null,
  code text not null,
  summary text not null,
  details_json text not null default '{}',
  created_at text not null,
  resolved_at text,
  unique(run_id,entity_kind,entity_id,code)
);
create index if not exists brain_reconciliation_findings_run_idx
  on brain_reconciliation_findings(run_id,severity,code);

drop trigger if exists superbrain_event_wake_enqueue;
create trigger superbrain_event_wake_enqueue
after insert on brain_events
begin
  insert or ignore into brain_wake_queue(
    subscription_id,event_id,subscriber,state,attempts,available_epoch,
    created_at,updated_at
  )
  select
    s.subscription_id,new.id,s.subscriber,'PENDING',0,new.ts_epoch,
    new.ts,new.ts
  from brain_event_subscriptions s
  where s.enabled=1
    and (s.event_type='*' or s.event_type=new.event_type)
    and new.priority <= s.priority_ceiling
    and (s.task_id is null or s.task_id=new.task_id)
    and s.subscriber <> new.sender;
end;
