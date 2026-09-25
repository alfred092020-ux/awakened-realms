from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_ROOT = Path("/home/ubuntu/logres")
CHAT_CONTRACT_STATES = frozenset({
    "RUNNING",
    "CONTINUE_REQUESTED",
    "WAITING_USER",
    "PAUSED",
    "DONE",
})
VALID_CHAT_CONTRACT_STATES = set(CHAT_CONTRACT_STATES)
SCHEMA_VERSION = 1


def _iso_from_epoch(value: float) -> str:
    return datetime.fromtimestamp(
        float(value),
        tz=timezone.utc,
    ).isoformat(timespec="seconds")


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, 0o600)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


class ChatContractStore:
    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        *,
        clock=time.time,
    ):
        self.root = Path(root)
        self.clock = clock
        device_dir = self.root / "control/android-device"
        self.path = Path(
            os.environ.get(
                "LOGRES_CHAT_CONTRACT_PATH",
                str(device_dir / "chat-contracts.json"),
            )
        )
        self.lock_path = Path(f"{self.path}.lock")

    @contextmanager
    def _locked(self, *, exclusive: bool) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            try:
                os.chmod(self.lock_path, 0o600)
            except OSError:
                pass
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH,
            )
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _load_unlocked(self) -> dict:
        if not self.path.is_file():
            return {
                "schema": SCHEMA_VERSION,
                "chats": {},
            }
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            value = {}
        if not isinstance(value, dict):
            value = {}
        chats = value.get("chats")
        if not isinstance(chats, dict):
            chats = {}
        return {
            "schema": SCHEMA_VERSION,
            "chats": chats,
        }

    def _missing(self, chat_id: str) -> dict:
        return {
            "chat_id": str(chat_id),
            "exists": False,
            "state": "PAUSED",
            "state_epoch": 0.0,
            "state_at": None,
            "updated_epoch": 0.0,
            "updated_at": None,
            "heartbeat_epoch": 0.0,
            "heartbeat_at": None,
            "heartbeat_sequence": 0,
            "turn_id": None,
            "sequence": 0,
            "note": "",
        }

    def _record(self, chat_id: str, value: object) -> dict:
        if not isinstance(value, dict):
            return self._missing(chat_id)
        state = str(value.get("state") or "PAUSED").upper()
        if state not in CHAT_CONTRACT_STATES:
            state = "PAUSED"
        return {
            **self._missing(chat_id),
            **value,
            "chat_id": str(chat_id),
            "exists": True,
            "state": state,
        }

    def read(self, chat_id: str) -> dict:
        key = str(chat_id).strip()
        if not key:
            raise ValueError("chat_id must be non-empty")
        with self._locked(exclusive=False):
            value = self._load_unlocked()
            return self._record(
                key,
                value["chats"].get(key),
            )

    def get(self, chat_id: str) -> dict | None:
        value = self.read(chat_id)
        return value if value["exists"] else None

    def list(self) -> dict[str, dict]:
        with self._locked(exclusive=False):
            value = self._load_unlocked()
            return {
                str(chat_id): self._record(chat_id, record)
                for chat_id, record in value["chats"].items()
                if isinstance(record, dict)
            }

    def heartbeat_age(self, contract: dict) -> float:
        epoch = float(contract.get("heartbeat_epoch") or 0.0)
        if epoch <= 0:
            return float("inf")
        return max(0.0, float(self.clock()) - epoch)

    def set_state(
        self,
        chat_id: str,
        state: str,
        *,
        note: str = "",
        reason: str | None = None,
    ) -> dict:
        key = str(chat_id).strip()
        target = str(state).strip().upper()
        if not key:
            raise ValueError("chat_id must be non-empty")
        if target not in CHAT_CONTRACT_STATES:
            raise ValueError(f"invalid contract state: {state!r}")
        if reason is not None and not note:
            note = str(reason)

        now = float(self.clock())
        timestamp = _iso_from_epoch(now)
        with self._locked(exclusive=True):
            value = self._load_unlocked()
            current = self._record(
                key,
                value["chats"].get(key),
            )
            current_state = str(current["state"]).upper()
            turn_id = current.get("turn_id")
            if target == "RUNNING" and current_state != "RUNNING":
                turn_id = uuid.uuid4().hex
            elif target == "RUNNING" and not turn_id:
                turn_id = uuid.uuid4().hex

            record = {
                **current,
                "chat_id": key,
                "exists": True,
                "state": target,
                "state_epoch": now,
                "state_at": timestamp,
                "updated_epoch": now,
                "updated_at": timestamp,
                "turn_id": turn_id,
                "sequence": int(current.get("sequence", 0) or 0) + 1,
                "note": str(note or ""),
            }
            if target == "RUNNING":
                record["heartbeat_epoch"] = now
                record["heartbeat_at"] = timestamp
                record["heartbeat_sequence"] = (
                    int(current.get("heartbeat_sequence", 0) or 0) + 1
                )

            value["chats"][key] = record
            _atomic_json(self.path, value)
        return dict(record)

    def heartbeat(
        self,
        chat_id: str,
        *,
        note: str = "",
        reason: str | None = None,
    ) -> dict:
        key = str(chat_id).strip()
        if not key:
            raise ValueError("chat_id must be non-empty")
        if reason is not None and not note:
            note = str(reason)
        now = float(self.clock())
        timestamp = _iso_from_epoch(now)

        with self._locked(exclusive=True):
            value = self._load_unlocked()
            current = self._record(
                key,
                value["chats"].get(key),
            )
            if not current["exists"]:
                raise ValueError(f"no contract exists for {key}")
            if str(current["state"]).upper() != "RUNNING":
                raise ValueError(
                    f"cannot heartbeat {key} while state={current.get('state')!r}"
                )
            record = {
                **current,
                "heartbeat_epoch": now,
                "heartbeat_at": timestamp,
                "heartbeat_sequence": (
                    int(current.get("heartbeat_sequence", 0) or 0) + 1
                ),
                "heartbeat_note": str(note or ""),
            }
            value["chats"][key] = record
            _atomic_json(self.path, value)
        return dict(record)

    def ensure(
        self,
        chat_id: str,
        *,
        default_state: str = "PAUSED",
        note: str = "",
        reason: str | None = None,
    ) -> dict:
        current = self.get(chat_id)
        if current is not None:
            return current
        if reason is not None and not note:
            note = str(reason)
        return self.set_state(
            chat_id,
            default_state,
            note=note,
        )

