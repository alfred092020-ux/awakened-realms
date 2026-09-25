from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

_SECRET_KEY_RE = re.compile(
    r"(?:^|[_-])(api[_-]?key|access[_-]?token|refresh[_-]?token|"
    r"authorization|cookie|client[_-]?secret|password|passwd|secret)(?:$|[_-])",
    re.IGNORECASE,
)

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

def _normalized_key(key: object) -> str:
    raw = str(key)
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", raw)
    return snake.replace("-", "_").lower()

def validate_sanitized_payload(value: Any, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalized_key(key)
            if _SECRET_KEY_RE.search(normalized):
                raise ValueError(f"secret-bearing key rejected at {path}.{key}")
            validate_sanitized_payload(item, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_sanitized_payload(item, path=f"{path}[{index}]")

def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists integration_targets(
          provider text not null,
          target_key text not null,
          account_ref text not null default '',
          purpose text not null default '',
          enabled integer not null default 1,
          execution_mode text not null default 'connector',
          read_policy_json text not null default '{}',
          write_policy_json text not null default '{}',
          metadata_json text not null default '{}',
          created_at text not null default (datetime('now')),
          updated_at text not null default (datetime('now')),
          primary key(provider,target_key)
        );

        create table if not exists integration_bindings(
          id integer primary key autoincrement,
          provider text not null,
          logical_slot text not null default 'default',
          canonical_entity_type text not null,
          canonical_entity_id text not null,
          provider_entity_type text not null,
          provider_entity_id text not null,
          provider_url text,
          projected_hash text,
          observed_hash text,
          sync_state text not null default 'BOUND',
          metadata_json text not null default '{}',
          created_at text not null default (datetime('now')),
          updated_at text not null default (datetime('now')),
          unique(provider,provider_entity_type,provider_entity_id),
          unique(provider,canonical_entity_type,canonical_entity_id,logical_slot)
        );

        create table if not exists integration_intents(
          id integer primary key autoincrement,
          dedupe_key text not null unique,
          provider text not null,
          target_key text not null,
          operation text not null,
          action_class text not null,
          canonical_entity_type text not null,
          canonical_entity_id text not null,
          logical_slot text not null default 'default',
          payload_json text not null default '{}',
          payload_hash text not null,
          projection_hash text,
          priority integer not null default 100,
          state text not null default 'NEW',
          attempt_count integer not null default 0,
          required_capability text,
          created_by text not null,
          source_event_id integer,
          task_id text,
          last_error text,
          superseded_by integer,
          created_at text not null default (datetime('now')),
          updated_at text not null default (datetime('now'))
        );
        create index if not exists integration_intents_queue_idx
          on integration_intents(state,provider,priority,id);
        create index if not exists integration_intents_entity_idx
          on integration_intents(
            provider,canonical_entity_type,canonical_entity_id,logical_slot,id
          );

        create table if not exists integration_claims(
          intent_id integer primary key,
          chat_id text not null,
          lease_token text not null unique,
          claimed_at text not null,
          lease_until_epoch real not null,
          renewed_at text not null,
          foreign key(intent_id) references integration_intents(id) on delete cascade
        );

        create table if not exists integration_receipts(
          id integer primary key autoincrement,
          receipt_key text not null unique,
          intent_id integer not null,
          provider text not null,
          operation text not null,
          outcome text not null,
          provider_entity_type text,
          provider_entity_id text,
          provider_url text,
          provider_version text,
          observed_hash text,
          response_metadata_json text not null default '{}',
          error_class text,
          error_detail text,
          chat_id text not null,
          attempt_number integer not null,
          created_at text not null default (datetime('now')),
          foreign key(intent_id) references integration_intents(id)
        );
        create index if not exists integration_receipts_intent_idx
          on integration_receipts(intent_id,id);

        create table if not exists integration_cursors(
          provider text not null,
          target_key text not null,
          cursor_name text not null,
          cursor_value text not null,
          metadata_json text not null default '{}',
          updated_at text not null default (datetime('now')),
          primary key(provider,target_key,cursor_name)
        );

        create table if not exists integration_proposals(
          id integer primary key autoincrement,
          dedupe_key text not null unique,
          provider text not null,
          target_key text not null,
          provider_entity_id text,
          canonical_entity_type text,
          canonical_entity_id text,
          change_type text not null,
          observed_json text not null,
          canonical_json text,
          risk_class text not null,
          disposition text not null default 'OPEN',
          reviewer text,
          review_note text,
          created_at text not null default (datetime('now')),
          updated_at text not null default (datetime('now'))
        );
        create index if not exists integration_proposals_queue_idx
          on integration_proposals(disposition,risk_class,provider,id);

        create table if not exists integration_capabilities(
          chat_id text not null,
          capability text not null,
          target_key text not null default '',
          expires_at_epoch real not null,
          metadata_json text not null default '{}',
          updated_at text not null default (datetime('now')),
          primary key(chat_id,capability,target_key)
        );
        create index if not exists integration_capabilities_live_idx
          on integration_capabilities(capability,expires_at_epoch);
        """
    )
    conn.commit()
