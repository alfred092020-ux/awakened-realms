from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from logres_chat_wake import ChatWakeBridge, bounds_center, inspect_chat_ui

DEFAULT_ROOT = Path("/home/ubuntu/logres")
WORKED_TIMER = re.compile(r"^Worked for\s+\d+(?:m\s*)?(?:\d+s)?$", re.I)
TRANSIENT_UI = {
    "Stop", "Send", "Send Message", "Attachment", "Dictation", "Follow up",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_iso_epoch(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            os.unlink(temp)
        except FileNotFoundError:
            pass


def visible_activity_digest(xml_text: str) -> str:
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_text)
    values: list[str] = []
    for node in root.iter("node"):
        for key in ("text", "content-desc"):
            value = str(node.attrib.get(key) or "").strip()
            if not value or value in TRANSIENT_UI or WORKED_TIMER.match(value):
                continue
            values.append(value)
    payload = "\n".join(values[-120:])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def recovery_action(
    *,
    stale_age: float,
    stale_seconds: float,
    stop_present: bool,
    digest_changed: bool,
    stuck_age: float,
    stuck_seconds: float,
    cooldown_age: float,
    cooldown_seconds: float,
) -> str:
    if stale_age < stale_seconds:
        return "FRESH"
    if cooldown_age < cooldown_seconds:
        return "COOLDOWN"
    if not stop_present:
        return "RESUME"
    if digest_changed or stuck_age < stuck_seconds:
        return "OBSERVE"
    return "STOP_AND_RESUME"


class ChatPeerWatchdog:
    def __init__(self, root: str | Path = DEFAULT_ROOT, *, clock=time.time, sleeper=time.sleep):
        self.root = Path(root)
        self.clock = clock
        self.sleeper = sleeper
        device_dir = self.root / "control/android-device"
        self.runtime_config = Path(
            os.environ.get(
                "LOGRES_CHAT_WATCHDOG_CONFIG",
                str(device_dir / "chat-watchdog.json"),
            )
        )
        self.default_config = self.root / "config/chat_watchdog.default.json"
        self.state_path = device_dir / "chat-watchdog-state.json"
        self.audit_path = device_dir / "chat-watchdog-audit.jsonl"
        self.targets_dir = device_dir / "chat-watchdog-targets"
        self.db_path = self.root / "control/control.sqlite"

    def load_config(self) -> dict:
        source = self.runtime_config if self.runtime_config.is_file() else self.default_config
        data = json.loads(source.read_text())
        if not isinstance(data, dict):
            raise ValueError("chat watchdog config must be an object")
        data["_source"] = str(source)
        return data

    def load_state(self) -> dict:
        if not self.state_path.is_file():
            return {"targets": {}}
        try:
            value = json.loads(self.state_path.read_text())
        except Exception:
            value = {}
        if not isinstance(value, dict):
            value = {}
        value.setdefault("targets", {})
        return value

    def save_state(self, state: dict) -> None:
        atomic_json(self.state_path, state)

    def audit(self, payload: dict) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": utc_now(), **payload}
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    def _brain_state(self, chat_id: str) -> dict:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma busy_timeout=15000")
        member = conn.execute(
            "select status,last_seen_epoch from brain_members where chat_id=?",
            (chat_id,),
        ).fetchone()
        leases = conn.execute(
            """select task_id,lease_until_epoch,renewed_at,progress,note
                 from brain_task_leases
                where chat_id=? and lease_until_epoch>?
                order by lease_until_epoch desc""",
            (chat_id, self.clock()),
        ).fetchall()
        conn.close()
        lease_activity = max(
            (parse_iso_epoch(row["renewed_at"]) for row in leases),
            default=0.0,
        )
        member_seen = float(member["last_seen_epoch"] or 0.0) if member else 0.0
        return {
            "member_status": str(member["status"]) if member else "MISSING",
            "last_activity_epoch": max(member_seen, lease_activity),
            "active_tasks": [str(row["task_id"]) for row in leases],
        }

    def _bridge_config(self, target: dict, common: dict) -> Path:
        chat_id = str(target["chat_id"])
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", chat_id)
        path = self.targets_dir / f"{safe}.json"
        message = str(target.get("resume_message") or "Continue Logres work.")
        payload = {
            "enabled": True,
            "target_name": str(target.get("name") or chat_id),
            "target_url": str(target["target_url"]),
            "target_semantic_labels": list(target.get("semantic_labels") or []),
            "min_interval_seconds": 0,
            "settle_seconds": float(common.get("settle_seconds", 1.2)),
            "allow_low_battery_wake": bool(common.get("allow_low_battery_wake", False)),
            "approved_messages": {"resume": message},
        }
        atomic_json(path, payload)
        return path

    def _bridge(self, target: dict, common: dict) -> ChatWakeBridge:
        bridge = ChatWakeBridge(self.root, clock=self.clock, sleeper=self.sleeper)
        bridge.runtime_config = self._bridge_config(target, common)
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(target["chat_id"]))
        bridge.state_path = self.root / "control/android-device" / f"chat-watchdog-bridge-{safe}.json"
        bridge.audit_path = self.root / "control/android-device" / "chat-bridge-audit.jsonl"
        return bridge

    def _response_probe(self, bridge: ChatWakeBridge, before_digest: str, verify_seconds: float) -> str:
        self.sleeper(1.0)
        first_xml = bridge._ui_xml()
        first = inspect_chat_ui(first_xml, [])
        first_digest = visible_activity_digest(first_xml)
        if first["stop_bounds"]:
            return "RESPONDING"
        self.sleeper(verify_seconds)
        final_xml = bridge._ui_xml()
        final = inspect_chat_ui(final_xml, [])
        final_digest = visible_activity_digest(final_xml)
        if final["stop_bounds"]:
            return "RESPONDING"
        if final_digest != first_digest or final_digest != before_digest:
            return "RESPONDED"
        return "NO_RESPONSE"

    def _send_resume(self, bridge: ChatWakeBridge, target: dict, common: dict, *, stopped: bool) -> dict:
        if stopped:
            self.sleeper(float(common.get("stop_wait_seconds", 7)))
        command_id = f"watchdog-{target['chat_id']}-{int(self.clock())}"
        sent = bridge.send("resume", command_id)
        if sent.get("result") != "SENT":
            return {"result": str(sent.get("result") or "SEND_FAILED"), "sent": sent}
        before = visible_activity_digest(bridge._ui_xml())
        response = self._response_probe(
            bridge,
            before,
            float(common.get("verify_after_seconds", 8)),
        )
        return {"result": response, "sent": sent}

    def tick_target(self, target: dict, common: dict, state: dict) -> dict:
        chat_id = str(target["chat_id"])
        brain = self._brain_state(chat_id)
        always_watch = bool(target.get("always_watch", False))
        if not always_watch and not brain["active_tasks"]:
            return {"chat_id": chat_id, "result": "NO_ACTIVE_WORK", "brain": brain}

        now = self.clock()
        stale_seconds = float(target.get("stale_seconds", common.get("stale_seconds", 300)))
        stuck_seconds = float(target.get("stuck_seconds", common.get("stuck_seconds", 300)))
        cooldown_seconds = float(target.get("cooldown_seconds", common.get("cooldown_seconds", 600)))
        stale_age = max(0.0, now - float(brain["last_activity_epoch"] or 0.0))
        target_state = state.setdefault("targets", {}).setdefault(chat_id, {})
        last_recovery = float(target_state.get("last_recovery_epoch", 0.0) or 0.0)
        cooldown_age = max(0.0, now - last_recovery)

        if stale_age < stale_seconds:
            target_state.pop("stuck_since_epoch", None)
            target_state.pop("last_digest", None)
            return {"chat_id": chat_id, "result": "FRESH", "stale_age": stale_age, "brain": brain}

        bridge = self._bridge(target, common)
        opened = bridge.wake()
        if opened.get("result") != "NATIVE_EXACT_CHAT":
            return {"chat_id": chat_id, "result": str(opened.get("result")), "open": opened, "brain": brain}

        xml_text = bridge._ui_xml()
        ui = inspect_chat_ui(xml_text, [])
        digest = visible_activity_digest(xml_text)
        stop_present = bool(ui["stop_bounds"])
        previous_digest = str(target_state.get("last_digest") or "")
        digest_changed = bool(previous_digest and previous_digest != digest)
        if not previous_digest or digest_changed:
            target_state["stuck_since_epoch"] = now
        stuck_since = float(target_state.get("stuck_since_epoch", now) or now)
        stuck_age = max(0.0, now - stuck_since)

        action = recovery_action(
            stale_age=stale_age,
            stale_seconds=stale_seconds,
            stop_present=stop_present,
            digest_changed=digest_changed,
            stuck_age=stuck_age,
            stuck_seconds=stuck_seconds,
            cooldown_age=cooldown_age,
            cooldown_seconds=cooldown_seconds,
        )
        target_state["last_digest"] = digest
        target_state["last_seen_stop"] = stop_present
        target_state["last_checked_epoch"] = now

        if action in {"FRESH", "COOLDOWN", "OBSERVE"}:
            return {
                "chat_id": chat_id,
                "result": action,
                "stale_age": stale_age,
                "stuck_age": stuck_age,
                "stop_present": stop_present,
                "brain": brain,
            }

        stopped = False
        if action == "STOP_AND_RESUME":
            if len(ui["stop_bounds"]) != 1:
                return {"chat_id": chat_id, "result": "STOP_AMBIGUOUS", "ui": ui}
            x, y = bounds_center(ui["stop_bounds"][0])
            bridge.transport.shell(f"input tap {x} {y}")
            stopped = True

        outcome = self._send_resume(bridge, target, common, stopped=stopped)
        target_state["last_recovery_epoch"] = now
        target_state["last_recovery_result"] = outcome["result"]
        target_state["stuck_since_epoch"] = now
        self.audit(
            {
                "chat_id": chat_id,
                "action": action,
                "stopped": stopped,
                "result": outcome["result"],
                "active_tasks": brain["active_tasks"],
            }
        )
        return {
            "chat_id": chat_id,
            "result": outcome["result"],
            "action": action,
            "stopped": stopped,
            "brain": brain,
        }

    def tick(self) -> dict:
        config = self.load_config()
        if not bool(config.get("enabled", False)):
            return {"result": "DISABLED", "source": config.get("_source")}
        state = self.load_state()
        common = dict(config.get("policy") or {})
        results = []
        for target in list(config.get("targets") or []):
            if not bool(target.get("enabled", True)):
                continue
            try:
                results.append(self.tick_target(dict(target), common, state))
            except Exception as exc:
                results.append(
                    {
                        "chat_id": str(target.get("chat_id") or ""),
                        "result": "ERROR",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        self.save_state(state)
        return {"result": "OK", "targets": results, "source": config.get("_source")}

