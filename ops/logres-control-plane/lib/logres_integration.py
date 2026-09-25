from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
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

def register_target(
    conn: sqlite3.Connection,
    *,
    provider: str,
    target_key: str,
    account_ref: str = "",
    purpose: str = "",
    enabled: bool = True,
    execution_mode: str = "connector",
    read_policy: dict | None = None,
    write_policy: dict | None = None,
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    for payload in (read_policy or {}, write_policy or {}, metadata or {}):
        validate_sanitized_payload(payload)
    conn.execute(
        """insert into integration_targets(
             provider,target_key,account_ref,purpose,enabled,execution_mode,
             read_policy_json,write_policy_json,metadata_json,updated_at
           ) values(?,?,?,?,?,?,?,?,?,datetime('now'))
           on conflict(provider,target_key) do update set
             account_ref=excluded.account_ref,purpose=excluded.purpose,
             enabled=excluded.enabled,execution_mode=excluded.execution_mode,
             read_policy_json=excluded.read_policy_json,
             write_policy_json=excluded.write_policy_json,
             metadata_json=excluded.metadata_json,updated_at=datetime('now')""",
        (
            provider, target_key, account_ref, purpose, int(bool(enabled)),
            execution_mode, canonical_json(read_policy or {}),
            canonical_json(write_policy or {}), canonical_json(metadata or {}),
        ),
    )
    conn.commit()
    return list_targets(conn, provider=provider, target_key=target_key)[0]

def list_targets(
    conn: sqlite3.Connection,
    *,
    provider: str | None = None,
    target_key: str | None = None,
) -> list[dict]:
    ensure_schema(conn)
    clauses = []
    params: list[object] = []
    if provider is not None:
        clauses.append("provider=?")
        params.append(provider)
    if target_key is not None:
        clauses.append("target_key=?")
        params.append(target_key)
    where = f" where {' and '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        "select provider,target_key,account_ref,purpose,enabled,execution_mode,"
        "read_policy_json,write_policy_json,metadata_json,created_at,updated_at "
        f"from integration_targets{where} order by provider,target_key",
        params,
    )
    out = []
    for row in rows:
        item = dict(row)
        item["enabled"] = bool(item["enabled"])
        item["read_policy"] = json.loads(item.pop("read_policy_json"))
        item["write_policy"] = json.loads(item.pop("write_policy_json"))
        item["metadata"] = json.loads(item.pop("metadata_json"))
        out.append(item)
    return out

def set_capabilities(
    conn: sqlite3.Connection,
    *,
    chat_id: str,
    capabilities: list[str],
    expires_at_epoch: float,
    target_key: str = "",
    metadata: dict | None = None,
) -> list[dict]:
    ensure_schema(conn)
    validate_sanitized_payload(metadata or {})
    conn.execute(
        "delete from integration_capabilities where chat_id=? and target_key=?",
        (chat_id, target_key),
    )
    for capability in sorted(set(capabilities)):
        conn.execute(
            """insert into integration_capabilities(
                 chat_id,capability,target_key,expires_at_epoch,metadata_json,updated_at
               ) values(?,?,?,?,?,datetime('now'))""",
            (
                chat_id, capability, target_key, float(expires_at_epoch),
                canonical_json(metadata or {}),
            ),
        )
    conn.commit()
    return list_capabilities(conn, chat_id=chat_id, now_epoch=0.0)

def list_capabilities(
    conn: sqlite3.Connection,
    *,
    chat_id: str | None = None,
    now_epoch: float = 0.0,
) -> list[dict]:
    ensure_schema(conn)
    clauses = ["expires_at_epoch>?"]
    params: list[object] = [float(now_epoch)]
    if chat_id is not None:
        clauses.append("chat_id=?")
        params.append(chat_id)
    rows = conn.execute(
        """select chat_id,capability,target_key,expires_at_epoch,metadata_json,updated_at
             from integration_capabilities
            where """ + " and ".join(clauses) +
        " order by chat_id,capability,target_key",
        params,
    )
    out = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        out.append(item)
    return out

def compatible_capabilities(
    conn: sqlite3.Connection,
    *,
    capability: str,
    target_key: str = "",
    now_epoch: float,
) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        """select chat_id,capability,target_key,expires_at_epoch,metadata_json,updated_at
             from integration_capabilities
            where capability=? and target_key=? and expires_at_epoch>?
            order by chat_id""",
        (capability, target_key, float(now_epoch)),
    )
    out = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        out.append(item)
    return out

_INTENT_TRANSITIONS = {
    "NEW": {"CLAIMED", "SUPERSEDED", "CANCELLED"},
    "CLAIMED": {"DISPATCHED", "NEW", "CANCELLED"},
    "DISPATCHED": {"SUCCEEDED", "FAILED", "RETRYABLE", "RECONCILING"},
    "RECONCILING": {"SUCCEEDED", "FAILED", "RETRYABLE"},
    "RETRYABLE": {"CLAIMED", "SUPERSEDED", "CANCELLED"},
}

class IntegrationStateConflict(RuntimeError):
    pass

def _intent_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    return item

def get_intent(conn: sqlite3.Connection, intent_id: int) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        "select * from integration_intents where id=?",
        (int(intent_id),),
    ).fetchone()
    if row is None:
        raise KeyError(f"integration intent not found: {intent_id}")
    return _intent_dict(row)

def list_intents(
    conn: sqlite3.Connection,
    *,
    state: str | None = None,
    provider: str | None = None,
    required_capability: str | None = None,
    limit: int = 100,
) -> list[dict]:
    ensure_schema(conn)
    clauses = []
    params: list[object] = []
    if state is not None:
        clauses.append("state=?")
        params.append(state)
    if provider is not None:
        clauses.append("provider=?")
        params.append(provider)
    if required_capability is not None:
        clauses.append("required_capability=?")
        params.append(required_capability)
    where = f" where {' and '.join(clauses)}" if clauses else ""
    params.append(max(1, int(limit)))
    rows = conn.execute(
        f"""select * from integration_intents{where}
             order by priority asc,id asc limit ?""",
        params,
    )
    return [_intent_dict(row) for row in rows]

def create_intent(
    conn: sqlite3.Connection,
    *,
    provider: str,
    target_key: str,
    operation: str,
    action_class: str,
    canonical_entity_type: str,
    canonical_entity_id: str,
    payload: dict,
    created_by: str,
    dedupe_key: str,
    logical_slot: str = "default",
    projection_hash: str | None = None,
    priority: int = 100,
    required_capability: str | None = None,
    source_event_id: int | None = None,
    task_id: str | None = None,
) -> dict:
    ensure_schema(conn)
    validate_sanitized_payload(payload)
    payload_json = canonical_json(payload)
    payload_hash = canonical_hash(payload)
    prior = conn.execute(
        "select id from integration_intents where dedupe_key=?",
        (dedupe_key,),
    ).fetchone()
    if prior is not None:
        return get_intent(conn, int(prior[0]))
    cur = conn.execute(
        """insert into integration_intents(
             dedupe_key,provider,target_key,operation,action_class,
             canonical_entity_type,canonical_entity_id,logical_slot,
             payload_json,payload_hash,projection_hash,priority,state,
             required_capability,created_by,source_event_id,task_id
           ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            dedupe_key, provider, target_key, operation, action_class,
            canonical_entity_type, canonical_entity_id, logical_slot,
            payload_json, payload_hash, projection_hash, int(priority), "NEW",
            required_capability, created_by, source_event_id, task_id,
        ),
    )
    new_id = int(cur.lastrowid)
    older = list(
        conn.execute(
            """select id from integration_intents
                where provider=? and canonical_entity_type=?
                  and canonical_entity_id=? and logical_slot=?
                  and id<>? and state in ('NEW','RETRYABLE')
                  and not exists (
                    select 1 from integration_claims c
                     where c.intent_id=integration_intents.id
                  )
                order by id""",
            (
                provider, canonical_entity_type, canonical_entity_id,
                logical_slot, new_id,
            ),
        )
    )
    for row in older:
        conn.execute(
            """update integration_intents
                  set state='SUPERSEDED',superseded_by=?,updated_at=datetime('now')
                where id=? and state in ('NEW','RETRYABLE')""",
            (new_id, int(row[0])),
        )
    conn.commit()
    return get_intent(conn, new_id)

def transition_intent(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    expected: str,
    new: str,
    last_error: str | None = None,
) -> dict:
    allowed = _INTENT_TRANSITIONS.get(expected, set())
    if new not in allowed:
        raise IntegrationStateConflict(
            f"invalid integration transition: {expected} -> {new}"
        )
    cursor = conn.execute(
        """update integration_intents
              set state=?,last_error=?,updated_at=datetime('now')
            where id=? and state=?""",
        (new, last_error, int(intent_id), expected),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise IntegrationStateConflict(
            f"intent {intent_id} was not in expected state {expected}"
        )
    conn.commit()
    return get_intent(conn, intent_id)

class IntegrationClaimConflict(RuntimeError):
    pass

def _begin_immediate(
    conn: sqlite3.Connection,
    *,
    attempts: int = 6,
    initial_delay_seconds: float = 0.02,
) -> None:
    delay = max(0.0, float(initial_delay_seconds))
    for attempt in range(max(1, int(attempts))):
        try:
            conn.execute("begin immediate")
            return
        except sqlite3.OperationalError as exc:
            detail = str(exc).lower()
            transient = (
                "database is locked" in detail
                or "database is busy" in detail
                or "database table is locked" in detail
            )
            if not transient or attempt + 1 >= attempts:
                raise
            if conn.in_transaction:
                conn.rollback()
            time.sleep(delay)
            delay = min(0.32, max(0.02, delay * 2.0))

def _claim_dict(row: sqlite3.Row) -> dict:
    return dict(row)

def claim_intent(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    chat_id: str,
    now_epoch: float,
    lease_seconds: float = 900.0,
    lease_token: str | None = None,
) -> dict:
    ensure_schema(conn)
    token = lease_token or uuid.uuid4().hex
    now_value = float(now_epoch)
    lease_until = now_value + float(lease_seconds)
    _begin_immediate(conn)
    try:
        intent = conn.execute(
            "select state from integration_intents where id=?",
            (int(intent_id),),
        ).fetchone()
        if intent is None:
            raise KeyError(f"integration intent not found: {intent_id}")
        existing = conn.execute(
            """select intent_id,chat_id,lease_token,claimed_at,
                      lease_until_epoch,renewed_at
                 from integration_claims where intent_id=?""",
            (int(intent_id),),
        ).fetchone()
        if existing is not None and float(existing["lease_until_epoch"]) > now_value:
            if existing["chat_id"] == chat_id and existing["lease_token"] == token:
                conn.execute(
                    """update integration_claims
                          set lease_until_epoch=?,renewed_at=datetime('now')
                        where intent_id=? and lease_token=?""",
                    (lease_until, int(intent_id), token),
                )
                conn.commit()
                row = conn.execute(
                    "select * from integration_claims where intent_id=?",
                    (int(intent_id),),
                ).fetchone()
                return _claim_dict(row)
            raise IntegrationClaimConflict(
                f"intent {intent_id} already claimed by {existing['chat_id']}"
            )
        if existing is not None:
            conn.execute(
                "delete from integration_claims where intent_id=?",
                (int(intent_id),),
            )
        if intent["state"] not in {"NEW", "RETRYABLE", "CLAIMED"}:
            raise IntegrationClaimConflict(
                f"intent {intent_id} cannot be claimed from state {intent['state']}"
            )
        conn.execute(
            """insert into integration_claims(
                 intent_id,chat_id,lease_token,claimed_at,lease_until_epoch,renewed_at
               ) values(?,?,?,datetime('now'),?,datetime('now'))""",
            (int(intent_id), chat_id, token, lease_until),
        )
        if intent["state"] in {"NEW", "RETRYABLE"}:
            conn.execute(
                """update integration_intents
                      set state='CLAIMED',updated_at=datetime('now')
                    where id=?""",
                (int(intent_id),),
            )
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    row = conn.execute(
        "select * from integration_claims where intent_id=?",
        (int(intent_id),),
    ).fetchone()
    return _claim_dict(row)

def renew_claim(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    lease_token: str,
    now_epoch: float,
    lease_seconds: float = 900.0,
) -> dict:
    ensure_schema(conn)
    lease_until = float(now_epoch) + float(lease_seconds)
    _begin_immediate(conn)
    try:
        cursor = conn.execute(
            """update integration_claims
                  set lease_until_epoch=?,renewed_at=datetime('now')
                where intent_id=? and lease_token=? and lease_until_epoch>?""",
            (lease_until, int(intent_id), lease_token, float(now_epoch)),
        )
        if cursor.rowcount != 1:
            raise IntegrationClaimConflict(
                f"claim for intent {intent_id} is missing, expired, or token-mismatched"
            )
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    row = conn.execute(
        "select * from integration_claims where intent_id=?",
        (int(intent_id),),
    ).fetchone()
    return _claim_dict(row)

def release_claim(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    lease_token: str,
) -> None:
    ensure_schema(conn)
    _begin_immediate(conn)
    try:
        cursor = conn.execute(
            "delete from integration_claims where intent_id=? and lease_token=?",
            (int(intent_id), lease_token),
        )
        if cursor.rowcount != 1:
            raise IntegrationClaimConflict(
                f"claim for intent {intent_id} is missing or token-mismatched"
            )
        conn.execute(
            """update integration_intents
                  set state='NEW',updated_at=datetime('now')
                where id=? and state='CLAIMED'""",
            (int(intent_id),),
        )
        conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
