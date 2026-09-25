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

def retry_allowed(intent: dict) -> bool:
    action_class = str(intent.get("action_class", "")).upper()
    state = str(intent.get("state", "")).upper()
    if action_class == "IRREVERSIBLE_SIDE_EFFECT":
        return False
    return state in {"RETRYABLE", "NEW"}

def classify_uncertain_failure(
    conn: sqlite3.Connection,
    intent_id: int,
    *,
    error_detail: str,
) -> dict:
    intent = get_intent(conn, intent_id)
    if intent["state"] != "DISPATCHED":
        raise IntegrationStateConflict(
            f"uncertain failure requires DISPATCHED state, got {intent['state']}"
        )
    action_class = str(intent["action_class"]).upper()
    if action_class == "READ_ONLY":
        return transition_intent(
            conn,
            intent_id,
            expected="DISPATCHED",
            new="RETRYABLE",
            last_error=error_detail,
        )
    return transition_intent(
        conn,
        intent_id,
        expected="DISPATCHED",
        new="RECONCILING",
        last_error=error_detail,
    )

def _binding_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["metadata"] = json.loads(item.pop("metadata_json"))
    return item

def upsert_binding(
    conn: sqlite3.Connection,
    *,
    provider: str,
    canonical_entity_type: str,
    canonical_entity_id: str,
    provider_entity_type: str,
    provider_entity_id: str,
    logical_slot: str = "default",
    provider_url: str | None = None,
    projected_hash: str | None = None,
    observed_hash: str | None = None,
    sync_state: str = "BOUND",
    metadata: dict | None = None,
) -> dict:
    ensure_schema(conn)
    validate_sanitized_payload(metadata or {})
    conn.execute(
        """insert into integration_bindings(
             provider,logical_slot,canonical_entity_type,canonical_entity_id,
             provider_entity_type,provider_entity_id,provider_url,
             projected_hash,observed_hash,sync_state,metadata_json,updated_at
           ) values(?,?,?,?,?,?,?,?,?,?,?,datetime('now'))
           on conflict(provider,canonical_entity_type,canonical_entity_id,logical_slot)
           do update set
             provider_entity_type=excluded.provider_entity_type,
             provider_entity_id=excluded.provider_entity_id,
             provider_url=excluded.provider_url,
             projected_hash=excluded.projected_hash,
             observed_hash=excluded.observed_hash,
             sync_state=excluded.sync_state,
             metadata_json=excluded.metadata_json,
             updated_at=datetime('now')""",
        (
            provider, logical_slot, canonical_entity_type, canonical_entity_id,
            provider_entity_type, provider_entity_id, provider_url,
            projected_hash, observed_hash, sync_state, canonical_json(metadata or {}),
        ),
    )
    conn.commit()
    return get_binding(
        conn,
        provider=provider,
        canonical_entity_type=canonical_entity_type,
        canonical_entity_id=canonical_entity_id,
        logical_slot=logical_slot,
    )

def get_binding(
    conn: sqlite3.Connection,
    *,
    provider: str,
    canonical_entity_type: str,
    canonical_entity_id: str,
    logical_slot: str = "default",
) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        """select * from integration_bindings
            where provider=? and canonical_entity_type=?
              and canonical_entity_id=? and logical_slot=?""",
        (provider, canonical_entity_type, canonical_entity_id, logical_slot),
    ).fetchone()
    if row is None:
        raise KeyError(
            f"binding not found: {provider}:{canonical_entity_type}:"
            f"{canonical_entity_id}:{logical_slot}"
        )
    return _binding_dict(row)

def list_bindings(
    conn: sqlite3.Connection,
    *,
    provider: str | None = None,
) -> list[dict]:
    ensure_schema(conn)
    if provider is None:
        rows = conn.execute(
            "select * from integration_bindings order by provider,id"
        )
    else:
        rows = conn.execute(
            "select * from integration_bindings where provider=? order by id",
            (provider,),
        )
    return [_binding_dict(row) for row in rows]

def _receipt_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["response_metadata"] = json.loads(item.pop("response_metadata_json"))
    return item

def list_receipts(
    conn: sqlite3.Connection,
    intent_id: int,
) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "select * from integration_receipts where intent_id=? order by id",
        (int(intent_id),),
    )
    return [_receipt_dict(row) for row in rows]

def append_receipt(
    conn: sqlite3.Connection,
    *,
    intent_id: int,
    receipt_key: str,
    outcome: str,
    chat_id: str,
    attempt_number: int,
    provider_entity_type: str | None = None,
    provider_entity_id: str | None = None,
    provider_url: str | None = None,
    provider_version: str | None = None,
    observed_hash: str | None = None,
    response_metadata: dict | None = None,
    error_class: str | None = None,
    error_detail: str | None = None,
    bind_on_success: bool = False,
) -> dict:
    ensure_schema(conn)
    validate_sanitized_payload(response_metadata or {})
    intent = get_intent(conn, intent_id)
    prior = conn.execute(
        "select * from integration_receipts where receipt_key=?",
        (receipt_key,),
    ).fetchone()
    if prior is not None:
        return _receipt_dict(prior)
    cur = conn.execute(
        """insert into integration_receipts(
             receipt_key,intent_id,provider,operation,outcome,
             provider_entity_type,provider_entity_id,provider_url,provider_version,
             observed_hash,response_metadata_json,error_class,error_detail,
             chat_id,attempt_number
           ) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            receipt_key, int(intent_id), intent["provider"], intent["operation"],
            outcome, provider_entity_type, provider_entity_id, provider_url,
            provider_version, observed_hash, canonical_json(response_metadata or {}),
            error_class, error_detail, chat_id, int(attempt_number),
        ),
    )
    conn.commit()
    receipt = conn.execute(
        "select * from integration_receipts where id=?",
        (int(cur.lastrowid),),
    ).fetchone()
    out = _receipt_dict(receipt)
    if (
        bind_on_success
        and outcome == "SUCCEEDED"
        and provider_entity_type
        and provider_entity_id
    ):
        upsert_binding(
            conn,
            provider=intent["provider"],
            logical_slot=intent["logical_slot"],
            canonical_entity_type=intent["canonical_entity_type"],
            canonical_entity_id=intent["canonical_entity_id"],
            provider_entity_type=provider_entity_type,
            provider_entity_id=provider_entity_id,
            provider_url=provider_url,
            projected_hash=intent["projection_hash"],
            observed_hash=observed_hash,
        )
    return out

def _cursor_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["metadata"] = json.loads(item.pop("metadata_json"))
    return item

def get_cursor(
    conn: sqlite3.Connection,
    *,
    provider: str,
    target_key: str,
    cursor_name: str,
) -> dict:
    ensure_schema(conn)
    row = conn.execute(
        """select * from integration_cursors
            where provider=? and target_key=? and cursor_name=?""",
        (provider, target_key, cursor_name),
    ).fetchone()
    if row is None:
        raise KeyError(f"cursor not found: {provider}:{target_key}:{cursor_name}")
    return _cursor_dict(row)

def _cursor_is_forward(current: str, new: str) -> bool:
    try:
        return float(new) >= float(current)
    except (TypeError, ValueError):
        return str(new) >= str(current)

def set_cursor(
    conn: sqlite3.Connection,
    *,
    provider: str,
    target_key: str,
    cursor_name: str,
    cursor_value: str,
    metadata: dict | None = None,
    monotonic: bool = False,
) -> dict:
    ensure_schema(conn)
    validate_sanitized_payload(metadata or {})
    existing = conn.execute(
        """select cursor_value from integration_cursors
            where provider=? and target_key=? and cursor_name=?""",
        (provider, target_key, cursor_name),
    ).fetchone()
    if (
        monotonic
        and existing is not None
        and not _cursor_is_forward(str(existing[0]), str(cursor_value))
    ):
        return get_cursor(
            conn,
            provider=provider,
            target_key=target_key,
            cursor_name=cursor_name,
        )
    conn.execute(
        """insert into integration_cursors(
             provider,target_key,cursor_name,cursor_value,metadata_json,updated_at
           ) values(?,?,?,?,?,datetime('now'))
           on conflict(provider,target_key,cursor_name) do update set
             cursor_value=excluded.cursor_value,
             metadata_json=excluded.metadata_json,
             updated_at=datetime('now')""",
        (
            provider, target_key, cursor_name, str(cursor_value),
            canonical_json(metadata or {}),
        ),
    )
    conn.commit()
    return get_cursor(
        conn,
        provider=provider,
        target_key=target_key,
        cursor_name=cursor_name,
    )

def _proposal_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["observed"] = json.loads(item.pop("observed_json"))
    canonical = item.pop("canonical_json")
    item["canonical"] = None if canonical is None else json.loads(canonical)
    return item

def create_proposal(
    conn: sqlite3.Connection,
    *,
    dedupe_key: str,
    provider: str,
    target_key: str,
    change_type: str,
    observed: dict,
    risk_class: str,
    provider_entity_id: str | None = None,
    canonical_entity_type: str | None = None,
    canonical_entity_id: str | None = None,
    canonical: dict | None = None,
) -> dict:
    ensure_schema(conn)
    validate_sanitized_payload(observed)
    if canonical is not None:
        validate_sanitized_payload(canonical)
    prior = conn.execute(
        "select * from integration_proposals where dedupe_key=?",
        (dedupe_key,),
    ).fetchone()
    if prior is not None:
        return _proposal_dict(prior)
    cur = conn.execute(
        """insert into integration_proposals(
             dedupe_key,provider,target_key,provider_entity_id,
             canonical_entity_type,canonical_entity_id,change_type,
             observed_json,canonical_json,risk_class
           ) values(?,?,?,?,?,?,?,?,?,?)""",
        (
            dedupe_key, provider, target_key, provider_entity_id,
            canonical_entity_type, canonical_entity_id, change_type,
            canonical_json(observed),
            None if canonical is None else canonical_json(canonical),
            risk_class,
        ),
    )
    conn.commit()
    row = conn.execute(
        "select * from integration_proposals where id=?",
        (int(cur.lastrowid),),
    ).fetchone()
    return _proposal_dict(row)

def list_proposals(
    conn: sqlite3.Connection,
    *,
    disposition: str | None = None,
    provider: str | None = None,
) -> list[dict]:
    ensure_schema(conn)
    clauses = []
    params: list[object] = []
    if disposition is not None:
        clauses.append("disposition=?")
        params.append(disposition)
    if provider is not None:
        clauses.append("provider=?")
        params.append(provider)
    where = f" where {' and '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"select * from integration_proposals{where} order by id",
        params,
    )
    return [_proposal_dict(row) for row in rows]

def disposition_proposal(
    conn: sqlite3.Connection,
    proposal_id: int,
    *,
    expected: str,
    disposition: str,
    reviewer: str,
    note: str = "",
) -> dict:
    allowed = {"ACCEPTED", "REJECTED", "NOOP", "SUPERSEDED", "NEEDS_HUMAN"}
    if disposition not in allowed:
        raise ValueError(f"invalid proposal disposition: {disposition}")
    cursor = conn.execute(
        """update integration_proposals
              set disposition=?,reviewer=?,review_note=?,updated_at=datetime('now')
            where id=? and disposition=?""",
        (disposition, reviewer, note, int(proposal_id), expected),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        raise IntegrationStateConflict(
            f"proposal {proposal_id} was not in expected disposition {expected}"
        )
    conn.commit()
    row = conn.execute(
        "select * from integration_proposals where id=?",
        (int(proposal_id),),
    ).fetchone()
    if row is None:
        raise KeyError(f"proposal not found: {proposal_id}")
    return _proposal_dict(row)
