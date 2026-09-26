from __future__ import annotations

import json
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from logres_chat_contract import ChatContractStore
from logres_chat_wake import ChatWakeBridge, validate_target_url

FIXED_COMMAND_KEY = "assigned-brain-task"
FIXED_DELEGATION_MESSAGE = (
    "Continue your assigned Logres Brain task. Read Brain scope and acceptance criteria before work."
)
TERMINAL_ASSIGNMENT_STATES = {"COMPLETE", "CANCELLED", "FAILED"}


def utc_now(epoch: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """create table if not exists devin_chatgpt_assignments(
             assignment_id text primary key,
             task_id text not null,
             member_id text not null,
             branch text,
             command_id text not null unique,
             status text not null,
             assigned_at text not null,
             wake_result text,
             wake_at text,
             acknowledged_at text,
             completed_at text,
             verification_status text,
             metadata_json text not null default '{}'
           )"""
    )
    conn.execute(
        "create index if not exists devin_chatgpt_assignments_task_idx on devin_chatgpt_assignments(task_id,status)"
    )
    conn.commit()


def load_policy(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("delegation policy must be an object")
    return value


def _capacity(root: Path, policy: dict) -> tuple[int, int]:
    path = Path(policy.get("capacity_state_path") or root / "control/capacity-state.json")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (0, 10**9)
    plan = state.get("plan") or {}
    signals = state.get("signals") or {}
    cap = int((plan.get("lane_caps") or {}).get("chatgpt") or 0)
    backlog = int((signals.get("verifier") or {}).get("backlog") or 0)
    return (max(0, cap), max(0, backlog))


def _target_config(root: Path, worker: dict) -> dict | None:
    try:
        path = Path(str(worker.get("target_config_path") or "")).resolve()
        allowed = (root / "control/android-device/chat-watchdog-targets").resolve()
        path.relative_to(allowed)
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not bool(value.get("enabled", False)):
            return None
        validate_target_url(str(value.get("target_url") or ""))
        return value
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def eligible_workers(
    conn: sqlite3.Connection,
    root: str | Path,
    policy: dict,
    contracts: ChatContractStore,
    *,
    now: float | None = None,
) -> list[dict]:
    ensure_schema(conn)
    if not bool(policy.get("enabled", False)):
        return []
    root = Path(root)
    now = time.time() if now is None else float(now)
    cap, backlog = _capacity(root, policy)
    if cap <= 0 or backlog >= int(policy.get("max_verifier_backlog", 6)):
        return []
    configured = [w for w in policy.get("workers", []) if isinstance(w, dict) and w.get("enabled", False)]
    active = 0
    configured_ids = {str(w.get("member_id") or "") for w in configured}
    if configured_ids:
        placeholders = ",".join("?" for _ in configured_ids)
        active = int(conn.execute(
            f"select count(*) from brain_task_leases where chat_id in ({placeholders}) and lease_until_epoch>?",
            (*sorted(configured_ids), now),
        ).fetchone()[0])
    if active >= cap:
        return []
    out: list[dict] = []
    for worker in configured:
        member_id = str(worker.get("member_id") or "").strip()
        session_key = str(worker.get("session_key") or "").strip()
        if not member_id or not session_key:
            continue
        member = conn.execute("select 1 from brain_members where chat_id=?", (member_id,)).fetchone()
        session = conn.execute(
            "select * from brain_agent_sessions where session_key=? and member_id=? and provider='chatgpt'",
            (session_key, member_id),
        ).fetchone()
        if member is None or session is None:
            continue
        if str(session["state"] or "").upper() not in {"AVAILABLE", "IDLE"}:
            continue
        if str(session["wake_method"] or "") != "phone_exact_chat":
            continue
        if conn.execute(
            "select 1 from brain_task_leases where chat_id=? and lease_until_epoch>? limit 1",
            (member_id, now),
        ).fetchone():
            continue
        contract = contracts.get(member_id)
        if contract is None or str(contract.get("state") or "").upper() != "DONE":
            continue
        target = _target_config(root, worker)
        if target is None:
            continue
        out.append({**worker, "member_id": member_id, "session_key": session_key, "target": target})
        if active + len(out) >= cap:
            break
    return out


class ConfiguredChatWakeBridge(ChatWakeBridge):
    def __init__(self, root: str | Path, target: dict):
        super().__init__(root)
        self.target = dict(target)

    def load_config(self) -> dict:
        return {
            **self.target,
            "approved_messages": {FIXED_COMMAND_KEY: FIXED_DELEGATION_MESSAGE},
        }


def _ready_task(conn: sqlite3.Connection, task_id: str | None = None) -> str | None:
    sql = """select t.id from tasks t left join task_metadata m on m.task_id=t.id
             where upper(coalesce(t.status,''))='READY' and t.owner is null
               and lower(coalesce(m.work_type,'implementation'))='implementation'"""
    args: tuple = ()
    if task_id:
        sql += " and t.id=?"
        args = (task_id,)
    sql += " order by coalesce(t.priority,9),t.id limit 1"
    row = conn.execute(sql, args).fetchone()
    return str(row[0]) if row else None


def _event(conn: sqlite3.Connection, *, sender: str, recipient: str, event_type: str, task_id: str, subject: str, body: str, dedupe: str, meta: dict, now: float) -> None:
    conn.execute(
        """insert or ignore into brain_events(ts_epoch,ts,sender,recipient,event_type,priority,task_id,subject,body,artifact_path,artifact_sha256,dedupe_key,meta_json)
           values(?,?,?,?,?,1,?,?,?,?,?,?,?)""",
        (now, utc_now(now), sender, recipient, event_type, task_id, subject, body, None, None, dedupe, json.dumps(meta, sort_keys=True)),
    )
    conn.commit()


def _acknowledged(conn: sqlite3.Connection, task_id: str, member_id: str, *, renewed_at: str, progress: int, event_id: int) -> bool:
    lease = conn.execute(
        "select renewed_at,coalesce(progress,0) progress from brain_task_leases where task_id=? and chat_id=?",
        (task_id, member_id),
    ).fetchone()
    if lease and (str(lease["renewed_at"]) != str(renewed_at) or int(lease["progress"] or 0) > int(progress)):
        return True
    return conn.execute(
        "select 1 from brain_events where id>? and task_id=? and sender=? and event_type='PROGRESS' limit 1",
        (event_id, task_id, member_id),
    ).fetchone() is not None


def dispatch_once(
    conn: sqlite3.Connection,
    root: str | Path,
    policy: dict,
    *,
    contracts: ChatContractStore | None = None,
    runner=subprocess.run,
    bridge_factory=None,
    task_id: str | None = None,
    clock=time.time,
    sleeper=time.sleep,
) -> dict:
    ensure_schema(conn)
    root = Path(root)
    contracts = contracts or ChatContractStore(root)
    workers = eligible_workers(conn, root, policy, contracts, now=clock())
    task = _ready_task(conn, task_id)
    if not workers:
        return {"status": "NO_ELIGIBLE_WORKER"}
    if not task:
        return {"status": "NO_READY_TASK"}
    worker = workers[0]
    member_id = worker["member_id"]
    argv = [
        str(root / "bin/logres-coordinator"), "acquire", member_id,
        "--task", task,
        "--minutes", str(int(policy.get("lease_minutes", 120))),
        "--max-active", str(int(policy.get("max_active_brain_workers", 6))),
    ]
    proc = runner(argv, text=True, capture_output=True, check=False, timeout=60)
    if int(proc.returncode) != 0:
        return {"status": "ASSIGNMENT_REJECTED", "task_id": task, "worker": member_id, "error": (proc.stderr or proc.stdout or "")[-1000:]}
    lease = conn.execute(
        "select branch,renewed_at,coalesce(progress,0) progress from brain_task_leases where task_id=? and chat_id=?",
        (task, member_id),
    ).fetchone()
    if lease is None:
        return {"status": "ASSIGNMENT_NOT_PROVEN", "task_id": task, "worker": member_id}
    baseline_event = int(conn.execute("select coalesce(max(id),0) from brain_events").fetchone()[0])
    assignment_id = "dcg-" + uuid.uuid4().hex
    command_id = "dcg-" + uuid.uuid4().hex[:24]
    now = float(clock())
    conn.execute(
        """insert into devin_chatgpt_assignments(assignment_id,task_id,member_id,branch,command_id,status,assigned_at,metadata_json)
           values(?,?,?,?,?,'ASSIGNED',?,?)""",
        (assignment_id, task, member_id, lease["branch"], command_id, utc_now(now), json.dumps({"session_key": worker["session_key"]}, sort_keys=True)),
    )
    conn.commit()
    bridge = (bridge_factory or (lambda r, t: ConfiguredChatWakeBridge(r, t)))(root, worker["target"])
    sent = bridge.send(FIXED_COMMAND_KEY, command_id)
    wake_result = str(sent.get("result") or "UNKNOWN")
    conn.execute(
        "update devin_chatgpt_assignments set wake_result=?,wake_at=?,status=? where assignment_id=?",
        (wake_result, utc_now(float(clock())), "SENT" if wake_result == "SENT" else "WAKE_DEFERRED", assignment_id),
    )
    conn.commit()
    _event(
        conn, sender="devin-lead", recipient=member_id, event_type="CHATGPT_WAKE", task_id=task,
        subject="Bounded ChatGPT worker wake", body=f"command_id={command_id} result={wake_result}",
        dedupe=f"devin-chatgpt-wake:{assignment_id}", meta={"assignment_id": assignment_id, "command_id": command_id, "wake_result": wake_result}, now=float(clock()),
    )
    if wake_result != "SENT":
        return {"status": "WAKE_DEFERRED", "task_id": task, "worker": member_id, "wake_result": wake_result, "assignment_id": assignment_id}
    try:
        contracts.set_state(member_id, "CONTINUE_REQUESTED", note=f"Brain task {task} assigned")
    except Exception:
        pass
    deadline = float(clock()) + max(0.0, float(policy.get("ack_timeout_seconds", 120)))
    acknowledged = False
    while True:
        if _acknowledged(conn, task, member_id, renewed_at=str(lease["renewed_at"]), progress=int(lease["progress"] or 0), event_id=baseline_event):
            acknowledged = True
            break
        if float(clock()) >= deadline:
            break
        sleeper(max(0.05, float(policy.get("poll_interval_seconds", 5))))
    status = "ACKED" if acknowledged else "SENT_UNACKNOWLEDGED"
    ack_at = utc_now(float(clock())) if acknowledged else None
    conn.execute(
        "update devin_chatgpt_assignments set status=?,acknowledged_at=? where assignment_id=?",
        (status, ack_at, assignment_id),
    )
    conn.commit()
    if acknowledged:
        _event(
            conn, sender="devin-lead", recipient="ALL", event_type="CHATGPT_ACK", task_id=task,
            subject="ChatGPT worker acknowledged assignment", body=f"assignment_id={assignment_id} member={member_id}",
            dedupe=f"devin-chatgpt-ack:{assignment_id}", meta={"assignment_id": assignment_id, "member_id": member_id}, now=float(clock()),
        )
    return {"status": status, "task_id": task, "worker": member_id, "assignment_id": assignment_id, "command_id": command_id}


def reconcile_assignments(conn: sqlite3.Connection, *, now_epoch: float | None = None) -> list[dict]:
    ensure_schema(conn)
    now_epoch = time.time() if now_epoch is None else float(now_epoch)
    updates: list[dict] = []
    rows = conn.execute(
        "select * from devin_chatgpt_assignments where status not in ('COMPLETE','CANCELLED','FAILED') order by assigned_at"
    ).fetchall()
    for row in rows:
        task = conn.execute("select status,branch from tasks where id=?", (row["task_id"],)).fetchone()
        if task and str(task["status"] or "").upper() == "DONE":
            branch = row["branch"] or task["branch"]
            verification = conn.execute(
                "select status from verification where ref=? order by ran_at desc limit 1", (branch,)
            ).fetchone()
            verification_status = str(verification[0]) if verification else "UNKNOWN"
            conn.execute(
                "update devin_chatgpt_assignments set status='COMPLETE',completed_at=?,verification_status=? where assignment_id=?",
                (utc_now(now_epoch), verification_status, row["assignment_id"]),
            )
            updates.append({"assignment_id": row["assignment_id"], "task_id": row["task_id"], "status": "COMPLETE", "verification_status": verification_status})
        elif conn.execute("select 1 from brain_task_leases where task_id=?", (row["task_id"],)).fetchone() is None:
            conn.execute("update devin_chatgpt_assignments set status='RECOVERABLE' where assignment_id=?", (row["assignment_id"],))
            updates.append({"assignment_id": row["assignment_id"], "task_id": row["task_id"], "status": "RECOVERABLE"})
    conn.commit()
    return updates
