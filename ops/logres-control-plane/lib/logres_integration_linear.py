from __future__ import annotations

import sqlite3
from typing import Any

from logres_integration import (
    canonical_hash,
    compatible_capabilities,
    create_intent,
    create_proposal,
    get_binding,
    list_bindings,
    list_targets,
    upsert_binding,
)

PROVIDER = "linear"
CANONICAL_ENTITY_TYPE = "brain_task"
PROVIDER_ENTITY_TYPE = "issue"
LINEAR_WRITE_CAPABILITY = "linear.issue.write"
DEFAULT_DEFAULT_MANAGED_FIELDS = ("title", "description", "priority")
ALLOWED_MANAGED_FIELDS = {"title", "description", "priority", "project", "labels"}
ALLOWED_MANAGED_FIELDS = ("title", "description", "priority", "project", "labels")
MAX_TITLE_CHARS = 160
MAX_DESCRIPTION_CHARS = 4000
MAX_ACCEPTANCE_ITEMS = 8
MAX_ACCEPTANCE_CHARS = 480


def _truncate(value: object, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _linear_priority(value: object) -> int:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        priority = 3
    if priority <= 0:
        return 1
    if priority == 1:
        return 2
    if priority == 2:
        return 3
    return 4


def _target(conn: sqlite3.Connection, target_key: str) -> dict:
    rows = list_targets(conn, provider=PROVIDER, target_key=target_key)
    if not rows:
        raise KeyError(f"Linear integration target not found: {target_key}")
    return rows[0]


def _managed_field_names(target: dict) -> tuple[str, ...]:
    configured = (target.get("write_policy") or {}).get("managed_fields")
    if not isinstance(configured, (list, tuple)):
        return DEFAULT_MANAGED_FIELDS
    requested = {str(item) for item in configured}
    fields = tuple(name for name in ALLOWED_MANAGED_FIELDS if name in requested)
    return fields or DEFAULT_MANAGED_FIELDS


def _labels(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted({_truncate(item, 100) for item in value if _truncate(item, 100)})[:20]


def _task_projection_source(conn: sqlite3.Connection, task_id: str) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
    row = conn.execute(
        """select t.id,t.priority,t.lane,t.title,t.status,
                  m.milestone,m.work_type,m.expected_minutes,m.concurrency_key
             from tasks t
             left join task_metadata m on m.task_id=t.id
            where t.id=?""",
        (task_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"Brain task not found: {task_id}")
    acceptance = list(
        conn.execute(
            """select ordinal,criterion from task_acceptance
                where task_id=? order by ordinal""",
            (task_id,),
        )
    )
    return row, acceptance


def _description(task: sqlite3.Row, acceptance: list[sqlite3.Row]) -> str:
    lines = [
        f"Brain task: `{task['id']}`",
        f"Status: {task['status'] or 'UNKNOWN'}",
        f"Priority: P{task['priority'] if task['priority'] is not None else '?'}",
        f"Lane: {task['lane'] or 'unspecified'}",
    ]
    if task["milestone"]:
        lines.append(f"Milestone: {task['milestone']}")
    if task["work_type"]:
        lines.append(f"Work type: {task['work_type']}")
    if task["expected_minutes"] is not None:
        lines.append(f"Expected: {int(task['expected_minutes'])}m")
    if acceptance:
        lines.extend(["", "Acceptance:"])
        for row in acceptance[:MAX_ACCEPTANCE_ITEMS]:
            criterion = _truncate(row["criterion"], MAX_ACCEPTANCE_CHARS)
            lines.append(f"{int(row['ordinal'])}. {criterion}")
    lines.extend(
        [
            "",
            "Managed projection only. Brain remains authoritative for leases, evidence, integration, and Git state.",
        ]
    )
    return _truncate("\n".join(lines), MAX_DESCRIPTION_CHARS)


def project_task(conn: sqlite3.Connection, task_id: str, target_key: str) -> dict[str, Any]:
    target = _target(conn, target_key)
    task, acceptance = _task_projection_source(conn, task_id)
    metadata = target.get("metadata") or {}
    team = _truncate(metadata.get("team"), 200)
    if not team:
        raise ValueError(f"Linear target {target_key!r} requires metadata.team")

    projected = {
        "title": _truncate(task["title"] or task_id, MAX_TITLE_CHARS),
        "description": _description(task, acceptance),
        "priority": _linear_priority(task["priority"]),
    }
    project = _truncate(metadata.get("project"), 200)
    labels = _labels(metadata.get("labels") or [])
    if project:
        projected["project"] = project
    if labels:
        projected["labels"] = labels
    managed_names = _managed_field_names(target)
    managed = {name: projected.get(name) for name in managed_names}
    create_payload: dict[str, Any] = {"team": team, **projected}

    configured = (target.get("write_policy") or {}).get("managed_fields")
    if isinstance(configured, list):
        managed_names = [
            str(name) for name in configured
            if str(name) in ALLOWED_MANAGED_FIELDS
        ]
    else:
        managed_names = list(DEFAULT_MANAGED_FIELDS)
    managed_fields = {
        name: create_payload[name]
        for name in managed_names
        if name in create_payload
    }
    return {
        "provider": PROVIDER,
        "target_key": target_key,
        "canonical_entity_type": CANONICAL_ENTITY_TYPE,
        "canonical_entity_id": task_id,
        "managed_fields": managed_fields,
        "create_payload": create_payload,
        "projection_hash": canonical_hash(managed_fields),
    }


def _binding_for_target(
    conn: sqlite3.Connection,
    task_id: str,
    target_key: str,
) -> dict[str, Any] | None:
    for slot in (target_key, "default"):
        try:
            return get_binding(
                conn,
                provider=PROVIDER,
                canonical_entity_type=CANONICAL_ENTITY_TYPE,
                canonical_entity_id=task_id,
                logical_slot=slot,
            )
        except KeyError:
            continue
    return None


def plan_task_sync(
    conn: sqlite3.Connection,
    task_id: str,
    target_key: str,
    *,
    chat_id: str,
    now_epoch: float,
) -> dict[str, Any]:
    try:
        target = _target(conn, target_key)
    except KeyError:
        return {"status": "TARGET_MISSING", "intent": None, "target_key": target_key}
    if not target["enabled"]:
        return {"status": "TARGET_DISABLED", "intent": None, "target_key": target_key}
    capabilities = compatible_capabilities(
        conn,
        capability=LINEAR_WRITE_CAPABILITY,
        target_key=target_key,
        now_epoch=now_epoch,
    )
    if not capabilities:
        return {
            "status": "MISSING_CAPABILITY",
            "intent": None,
            "target_key": target_key,
            "required_capability": LINEAR_WRITE_CAPABILITY,
        }

    projection = project_task(conn, task_id, target_key)
    binding = _binding_for_target(conn, task_id, target_key)

    if binding is not None and binding.get("projected_hash") == projection["projection_hash"]:
        return {"status": "IN_SYNC", "intent": None, "projection": projection, "binding": binding}

    if binding is None:
        operation = "issue.create"
        payload = projection["create_payload"]
    else:
        operation = "issue.update"
        payload = {"id": binding["provider_entity_id"], **projection["managed_fields"]}

    dedupe_key = (
        f"linear:{target_key}:{task_id}:{operation}:"
        f"{projection['projection_hash']}"
    )
    intent = create_intent(
        conn,
        provider=PROVIDER,
        target_key=target_key,
        operation=operation,
        action_class="REVERSIBLE_WRITE",
        canonical_entity_type=CANONICAL_ENTITY_TYPE,
        canonical_entity_id=task_id,
        logical_slot=(binding["logical_slot"] if binding is not None else target_key),
        payload=payload,
        projection_hash=projection["projection_hash"],
        required_capability=LINEAR_WRITE_CAPABILITY,
        created_by=chat_id,
        task_id=task_id,
        dedupe_key=dedupe_key,
        priority=20,
    )
    return {
        "status": "INTENT_CREATED",
        "operation": operation,
        "intent": intent,
        "projection": projection,
        "binding": binding,
    }


def observe_issue(
    conn: sqlite3.Connection,
    task_id: str,
    target_key: str,
    *,
    provider_entity_id: str,
    observed: dict[str, Any],
) -> dict[str, Any]:
    try:
        target = _target(conn, target_key)
    except KeyError:
        return {"status": "TARGET_MISSING", "proposal": None}
    if not target["enabled"]:
        return {"status": "TARGET_DISABLED", "proposal": None}
    projection = project_task(conn, task_id, target_key)
    expected = projection["managed_fields"]
    observed_managed = {key: observed.get(key) for key in expected}
    if "labels" in observed_managed:
        observed_managed["labels"] = _labels(observed_managed["labels"])
    observed_hash = canonical_hash(observed_managed)

    if observed_managed == expected:
        prior_binding = _binding_for_target(conn, task_id, target_key)
        binding = upsert_binding(
            conn,
            provider=PROVIDER,
            canonical_entity_type=CANONICAL_ENTITY_TYPE,
            canonical_entity_id=task_id,
            logical_slot=(prior_binding["logical_slot"] if prior_binding is not None else target_key),
            provider_entity_type=PROVIDER_ENTITY_TYPE,
            provider_entity_id=provider_entity_id,
            projected_hash=projection["projection_hash"],
            observed_hash=observed_hash,
            sync_state="BOUND",
        )
        return {"status": "IN_SYNC", "proposal": None, "binding": binding}

    proposal = create_proposal(
        conn,
        dedupe_key=(
            f"linear-drift:{target_key}:{task_id}:{provider_entity_id}:"
            f"{projection['projection_hash']}:{observed_hash}"
        ),
        provider=PROVIDER,
        target_key=target_key,
        provider_entity_id=provider_entity_id,
        canonical_entity_type=CANONICAL_ENTITY_TYPE,
        canonical_entity_id=task_id,
        change_type="MANAGED_FIELD_DRIFT",
        observed=observed_managed,
        canonical=expected,
        risk_class="HUMAN_REVIEW_REQUIRED",
    )
    prior_binding = _binding_for_target(conn, task_id, target_key)
    upsert_binding(
        conn,
        provider=PROVIDER,
        canonical_entity_type=CANONICAL_ENTITY_TYPE,
        canonical_entity_id=task_id,
        logical_slot=(prior_binding["logical_slot"] if prior_binding is not None else target_key),
        provider_entity_type=PROVIDER_ENTITY_TYPE,
        provider_entity_id=provider_entity_id,
        projected_hash=projection["projection_hash"],
        observed_hash=observed_hash,
        sync_state="DRIFT",
    )
    return {"status": "PROPOSAL_CREATED", "proposal": proposal, "projection": projection}
