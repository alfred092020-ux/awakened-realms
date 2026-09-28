from __future__ import annotations

import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Iterable


DEFAULT_RESOURCES: dict[str, int] = {
    "integration-promotion": 1,
    "nexus-live-runtime": 1,
    "privileged-executor": 1,
    "android-device": 1,
    "verify-heavy": 2,
    "verify-light": 4,
}

WORKLOAD_RESOURCES: dict[str, tuple[str, ...]] = {
    "verify": ("verify-heavy",),
    "promote": ("integration-promotion",),
    "deploy-live-nexus": ("nexus-live-runtime", "privileged-executor"),
    "device-qa": ("android-device",),
}


class ResourceBusy(RuntimeError):
    def __init__(self, resource: str, capacity: int, holders: int) -> None:
        self.resource = resource
        self.capacity = capacity
        self.holders = holders
        super().__init__(
            f"resource {resource!r} is busy ({holders}/{capacity} slots in use)"
        )


class UnknownResource(KeyError):
    pass


class RuntimeLaneStore:
    """Atomic lease manager for shared runtime resources.

    Source-code work remains parallel in isolated Git worktrees. Only tasks that
    need a scarce mutable runtime resource take one of these short leases.
    Multi-resource acquisition is all-or-nothing to avoid partial ownership and
    deadlocks between deploy/promotion operations.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runtime_resources (
                name TEXT PRIMARY KEY,
                capacity INTEGER NOT NULL CHECK (capacity > 0)
            );
            CREATE TABLE IF NOT EXISTS runtime_resource_leases (
                lease_id TEXT NOT NULL,
                resource TEXT NOT NULL,
                owner TEXT NOT NULL,
                task_id TEXT NOT NULL,
                acquired_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY (lease_id, resource),
                FOREIGN KEY (resource) REFERENCES runtime_resources(name)
            );
            CREATE INDEX IF NOT EXISTS idx_runtime_resource_leases_resource_expiry
                ON runtime_resource_leases(resource, expires_at);
            CREATE INDEX IF NOT EXISTS idx_runtime_resource_leases_lease
                ON runtime_resource_leases(lease_id);
            """
        )
        self.conn.commit()

    def define_resource(self, name: str, *, capacity: int) -> None:
        if not name or capacity < 1:
            raise ValueError("resource name and positive capacity are required")
        self.conn.execute(
            """
            INSERT INTO runtime_resources(name, capacity) VALUES(?, ?)
            ON CONFLICT(name) DO UPDATE SET capacity=excluded.capacity
            """,
            (name, capacity),
        )
        self.conn.commit()

    def define_defaults(self) -> None:
        for name, capacity in DEFAULT_RESOURCES.items():
            self.define_resource(name, capacity=capacity)

    def _purge_expired(self, now: int) -> None:
        self.conn.execute(
            "DELETE FROM runtime_resource_leases WHERE expires_at <= ?", (now,)
        )

    def acquire(
        self,
        resources: Iterable[str],
        *,
        owner: str,
        task_id: str,
        ttl_seconds: int,
        now: int | None = None,
    ) -> str:
        requested = tuple(sorted(set(resources)))
        if not requested:
            raise ValueError("at least one resource is required")
        if not owner or not task_id:
            raise ValueError("owner and task_id are required")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")

        at = int(time.time()) if now is None else int(now)
        lease_id = uuid.uuid4().hex
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            self._purge_expired(at)
            capacities: dict[str, int] = {}
            for resource in requested:
                row = self.conn.execute(
                    "SELECT capacity FROM runtime_resources WHERE name=?",
                    (resource,),
                ).fetchone()
                if row is None:
                    raise UnknownResource(resource)
                capacity = int(row["capacity"])
                holders = int(
                    self.conn.execute(
                        """
                        SELECT COUNT(*) AS n
                        FROM runtime_resource_leases
                        WHERE resource=? AND expires_at > ?
                        """,
                        (resource, at),
                    ).fetchone()["n"]
                )
                if holders >= capacity:
                    raise ResourceBusy(resource, capacity, holders)
                capacities[resource] = capacity

            expires_at = at + ttl_seconds
            self.conn.executemany(
                """
                INSERT INTO runtime_resource_leases(
                    lease_id, resource, owner, task_id, acquired_at, expires_at
                ) VALUES(?, ?, ?, ?, ?, ?)
                """,
                [
                    (lease_id, resource, owner, task_id, at, expires_at)
                    for resource in requested
                ],
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        return lease_id

    def renew(
        self,
        lease_id: str,
        *,
        ttl_seconds: int,
        now: int | None = None,
    ) -> int:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be positive")
        at = int(time.time()) if now is None else int(now)
        expires_at = at + ttl_seconds
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._purge_expired(at)
            cur = self.conn.execute(
                """
                UPDATE runtime_resource_leases
                SET expires_at=?
                WHERE lease_id=?
                """,
                (expires_at, lease_id),
            )
            self.conn.commit()
            return int(cur.rowcount)
        except Exception:
            self.conn.rollback()
            raise

    def release(self, lease_id: str) -> int:
        cur = self.conn.execute(
            "DELETE FROM runtime_resource_leases WHERE lease_id=?", (lease_id,)
        )
        self.conn.commit()
        return int(cur.rowcount)

    def status(self, *, now: int | None = None) -> dict[str, dict]:
        at = int(time.time()) if now is None else int(now)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self._purge_expired(at)
            resources = self.conn.execute(
                "SELECT name, capacity FROM runtime_resources ORDER BY name"
            ).fetchall()
            result: dict[str, dict] = {}
            for resource in resources:
                name = str(resource["name"])
                holders = self.conn.execute(
                    """
                    SELECT lease_id, owner, task_id, acquired_at, expires_at
                    FROM runtime_resource_leases
                    WHERE resource=? AND expires_at > ?
                    ORDER BY acquired_at, owner, task_id
                    """,
                    (name, at),
                ).fetchall()
                result[name] = {
                    "capacity": int(resource["capacity"]),
                    "available": max(0, int(resource["capacity"]) - len(holders)),
                    "holders": [dict(row) for row in holders],
                }
            self.conn.commit()
            return result
        except Exception:
            self.conn.rollback()
            raise


def workload_resources(workload: str) -> tuple[str, ...]:
    try:
        return WORKLOAD_RESOURCES[workload]
    except KeyError as exc:
        raise ValueError(f"unknown runtime workload: {workload}") from exc


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.")
    return value[:96] or "unnamed"


def sandbox_path(root: Path, owner: str, task_id: str, base_sha: str) -> Path:
    sha = re.sub(r"[^0-9A-Fa-f]", "", base_sha)[:12]
    if len(sha) < 7:
        raise ValueError("base_sha must contain at least seven hexadecimal characters")
    return root / _slug(owner) / _slug(task_id) / sha.lower()
