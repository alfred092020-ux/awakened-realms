from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def _ensure_runtime(conn) -> None:
    conn.execute(
        """create table if not exists devin_lead_runtime(
             singleton integer primary key check(singleton=1),
             instance_id text not null,
             lease_until_epoch real not null,
             renewed_at_epoch real not null
           )"""
    )


def load_lead_policy(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("lead policy must be an object")
    models = data.get("models", {})
    if bool(models.get("allow_paid_default", False)):
        raise ValueError("paid models may not be enabled by default")
    return data


def acquire_leader(conn, *, instance_id: str, now: float, ttl_seconds: int) -> bool:
    _ensure_runtime(conn)
    conn.execute("begin immediate")
    try:
        row = conn.execute(
            "select instance_id,lease_until_epoch from devin_lead_runtime where singleton=1"
        ).fetchone()
        if row and float(row[1]) > now and str(row[0]) != instance_id:
            conn.rollback()
            return False
        conn.execute(
            """insert into devin_lead_runtime(singleton,instance_id,lease_until_epoch,renewed_at_epoch)
               values(1,?,?,?)
               on conflict(singleton) do update set
                 instance_id=excluded.instance_id,
                 lease_until_epoch=excluded.lease_until_epoch,
                 renewed_at_epoch=excluded.renewed_at_epoch""",
            (instance_id, now + max(1, int(ttl_seconds)), now),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def renew_leader(conn, *, instance_id: str, now: float, ttl_seconds: int) -> bool:
    _ensure_runtime(conn)
    cur = conn.execute(
        """update devin_lead_runtime
             set lease_until_epoch=?, renewed_at_epoch=?
           where singleton=1 and instance_id=? and lease_until_epoch>?""",
        (now + max(1, int(ttl_seconds)), now, instance_id, now),
    )
    conn.commit()
    return cur.rowcount == 1


def read_pause(root: Path) -> dict:
    path = Path(root) / "control" / "devin-lead.pause"
    if not path.is_file():
        return {"paused": False, "reason": "", "path": str(path)}
    try:
        reason = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        reason = f"pause file unreadable: {exc}"
    return {"paused": True, "reason": reason or "operator pause", "path": str(path)}


def write_heartbeat(root: Path, payload: dict) -> None:
    path = Path(root) / "control" / "devin-lead-heartbeat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
