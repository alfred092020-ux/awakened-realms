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

from logres_chat_contract import CHAT_CONTRACT_STATES, ChatContractStore
from logres_chat_wake import CHATGPT_PACKAGE, ChatWakeBridge, bounds_center, inspect_chat_ui
from logres_phone_local_ai import PhoneLocalAI

DEFAULT_ROOT = Path("/home/ubuntu/logres")
WORKED_TIMER = re.compile(r"^Worked for\s+(?:(?P<minutes>\d+)m(?:\s+(?P<seconds>\d+)s)?|(?P<seconds_only>\d+)s)$", re.I)
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
        if node.attrib.get("package", "") not in {"", CHATGPT_PACKAGE}:
            continue
        for key in ("text", "content-desc"):
            value = str(node.attrib.get(key) or "").strip()
            if not value or value in TRANSIENT_UI or WORKED_TIMER.match(value):
                continue
            values.append(value)
    payload = "\n".join(values[-120:])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



VALID_CONTRACT_STATES = set(CHAT_CONTRACT_STATES)


def worked_timer_seconds(xml_text: str) -> int | None:
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_text)
    values: list[int] = []
    for node in root.iter("node"):
        if node.attrib.get("package", "") not in {"", CHATGPT_PACKAGE}:
            continue
        for key in ("text", "content-desc"):
            value = str(node.attrib.get(key) or "").strip()
            match = WORKED_TIMER.fullmatch(value)
            if not match:
                continue
            minutes = int(match.group("minutes") or 0)
            seconds = int(match.group("seconds") or match.group("seconds_only") or 0)
            values.append(minutes * 60 + seconds)
    return max(values) if values else None


def response_tail_digest(xml_text: str) -> str:
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_text)
    values: list[str] = []
    for node in root.iter("node"):
        if node.attrib.get("package", "") not in {"", CHATGPT_PACKAGE}:
            continue
        for key in ("text", "content-desc"):
            value = str(node.attrib.get(key) or "").strip()
            if not value or value in TRANSIENT_UI or WORKED_TIMER.fullmatch(value):
                continue
            folded = value.casefold()
            if any(token in folded for token in RATE_LIMIT_TEXT):
                continue
            if folded in {
                "copy",
                "read aloud",
                "good response",
                "bad response",
                "share",
                "regenerate",
            }:
                continue
            values.append(value)
    payload = "\\n".join(values[-16:])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()



RATE_LIMIT_TEXT = (
    "too many requests",
    "try again later",
    "you've reached",
    "you have reached",
)


def ui_rate_limited(xml_text: str) -> bool:
    folded = xml_text.casefold()
    return any(token in folded for token in RATE_LIMIT_TEXT)


def composer_text(ui: dict) -> str:
    values = [str(value or "").strip() for value in ui.get("editor_text", [])]
    if len(values) != 1:
        return ""
    return values[0]


def visible_chat_text(
    xml_text: str,
    *,
    max_chars: int = 2400,
) -> str:
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml_text)
    values: list[str] = []
    seen: set[str] = set()
    for node in root.iter("node"):
        if node.attrib.get("package", "") not in {
            "",
            CHATGPT_PACKAGE,
        }:
            continue
        for key in ("text", "content-desc"):
            value = str(
                node.attrib.get(key) or ""
            ).strip()
            if (
                not value
                or value in TRANSIENT_UI
                or WORKED_TIMER.fullmatch(value)
            ):
                continue
            if value in seen:
                continue
            seen.add(value)
            values.append(value)

    payload = "\n".join(values[-80:])
    if len(payload) <= max_chars:
        return payload
    return payload[-max_chars:]


def expired_running_no_stop_probe_action(
    *,
    initial_tail_digest: str,
    later_stop_present: bool,
    later_tail_digest: str,
) -> str:
    if later_stop_present:
        return "WORKING"
    if later_tail_digest != initial_tail_digest:
        return "WORKING"
    return "AMBIGUOUS"


def phone_ai_recovery_action(
    label: str,
    *,
    stop_count: int,
) -> str:
    value = str(label or "").upper()
    if value == "ACTIVE":
        return "AI_ACTIVE_HOLD"
    if value == "ENDED":
        return "RESUME"
    if value == "RATE_LIMITED":
        return "AI_RATE_LIMITED"
    if value == "WAITING_USER":
        return "AI_WAITING_USER"
    if value == "STUCK" and stop_count == 1:
        return "STOP_AND_RESUME"
    return "AI_HOLD"


def contract_gate_action(
    *,
    contract_state: str,
    heartbeat_age: float,
    heartbeat_timeout_seconds: float,
    continuation_age: float,
    continuation_grace_seconds: float,
) -> str:
    contract = str(contract_state or "").upper()
    if contract not in VALID_CONTRACT_STATES:
        raise ValueError(f"invalid chat contract state: {contract_state!r}")
    if contract in {"PAUSED", "WAITING_USER", "DONE"}:
        return "HOLD"
    if contract == "CONTINUE_REQUESTED":
        if continuation_age < continuation_grace_seconds:
            return "CONTINUATION_GRACE"
        return "PHONE_CHECK"
    if heartbeat_age < heartbeat_timeout_seconds:
        return "RUNNING_HEARTBEAT"
    return "PHONE_CHECK"


def contract_probe_action(
    *,
    contract_state: str,
    initial_stop_present: bool,
    initial_worked_seconds: int | None,
    initial_tail_digest: str,
    later_stop_present: bool,
    later_worked_seconds: int | None,
    later_tail_digest: str,
) -> str:
    contract = str(contract_state or "").upper()
    if contract not in VALID_CONTRACT_STATES:
        raise ValueError(f"invalid chat contract state: {contract_state!r}")
    if contract in {"PAUSED", "WAITING_USER", "DONE"}:
        return "HOLD"
    if not initial_stop_present or not later_stop_present:
        return "RESUME"
    timer_advanced = (
        initial_worked_seconds is not None
        and later_worked_seconds is not None
        and later_worked_seconds > initial_worked_seconds
    )
    tail_advanced = later_tail_digest != initial_tail_digest
    if timer_advanced or tail_advanced:
        return "WORKING"
    return "STOP_AND_RESUME"


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
    # Compatibility helper retained for callers/tests from the first watchdog
    # implementation. Runtime recovery now uses a same-run semantic probe so a
    # five-minute stale threshold cannot silently become a ten-minute restart.
    if stale_age < stale_seconds:
        return "FRESH"
    if cooldown_age < cooldown_seconds:
        return "COOLDOWN"
    if not stop_present:
        return "RESUME"
    if digest_changed or stuck_age < stuck_seconds:
        return "OBSERVE"
    return "STOP_AND_RESUME"


def same_run_probe_action(
    *,
    initial_stop_present: bool,
    initial_digest: str,
    later_stop_present: bool,
    later_digest: str,
) -> str:
    if not initial_stop_present:
        return "RESUME"
    if not later_stop_present:
        return "RESUME"
    if later_digest != initial_digest:
        return "WORKING"
    return "STOP_AND_RESUME"


class ChatPeerWatchdog:
    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        *,
        clock=time.time,
        sleeper=time.sleep,
        phone_ai: PhoneLocalAI | None = None,
    ):
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
        self.contracts = ChatContractStore(self.root, clock=self.clock)
        self.phone_ai = (
            phone_ai
            if phone_ai is not None
            else PhoneLocalAI(self.root)
        )

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
        use_runtime_contract = bool(
            target.get("use_runtime_contract", False)
        )

        if use_runtime_contract:
            contract = self.contracts.get(chat_id)
            if contract is None:
                contract = self.contracts.ensure(
                    chat_id,
                    default_state="PAUSED",
                    reason="watchdog fail-safe contract bootstrap",
                )
            contract_state = str(contract["state"]).upper()
            heartbeat_epoch = float(contract.get("heartbeat_epoch") or 0.0)
            heartbeat_age = (
                max(0.0, self.clock() - heartbeat_epoch)
                if heartbeat_epoch > 0
                else float("inf")
            )
            updated_epoch = float(contract.get("state_epoch") or 0.0)
        else:
            contract_state = str(
                target.get("contract_state", "PAUSED")
            ).upper()
            contract = {
                "state": contract_state,
                "exists": False,
                "updated_epoch": 0.0,
                "heartbeat_epoch": 0.0,
                "turn_id": None,
            }
            heartbeat_age = float("inf")
            updated_epoch = 0.0

        if contract_state not in VALID_CONTRACT_STATES:
            return {
                "chat_id": chat_id,
                "result": "INVALID_CONTRACT_STATE",
                "contract_state": contract_state,
                "brain": brain,
            }

        now = self.clock()
        heartbeat_timeout = float(
            target.get(
                "running_heartbeat_timeout_seconds",
                common.get("running_heartbeat_timeout_seconds", 300),
            )
        )
        continuation_grace = float(
            target.get(
                "continuation_grace_seconds",
                common.get("continuation_grace_seconds", 30),
            )
        )
        continuation_age = (
            max(0.0, now - updated_epoch)
            if updated_epoch > 0
            else float("inf")
        )
        gate = contract_gate_action(
            contract_state=contract_state,
            heartbeat_age=heartbeat_age,
            heartbeat_timeout_seconds=heartbeat_timeout,
            continuation_age=continuation_age,
            continuation_grace_seconds=continuation_grace,
        )

        if gate in {"HOLD", "RUNNING_HEARTBEAT", "CONTINUATION_GRACE"}:
            return {
                "chat_id": chat_id,
                "result": gate,
                "contract_state": contract_state,
                "heartbeat_age": heartbeat_age,
                "continuation_age": continuation_age,
                "turn_id": contract.get("turn_id"),
                "brain": brain,
            }

        target_state = state.setdefault("targets", {}).setdefault(chat_id, {})
        cooldown_seconds = float(
            target.get(
                "min_resume_interval_seconds",
                common.get(
                    "min_resume_interval_seconds",
                    common.get("cooldown_seconds", 300),
                ),
            )
        )
        probe_seconds = float(
            target.get(
                "stuck_probe_seconds",
                common.get("stuck_probe_seconds", 15),
            )
        )
        ambiguity_probe_seconds = float(
            target.get(
                "ambiguity_probe_seconds",
                common.get("ambiguity_probe_seconds", 5),
            )
        )
        phone_ai_ambiguity_enabled = bool(
            target.get(
                "phone_local_ai_ambiguity_enabled",
                common.get(
                    "phone_local_ai_ambiguity_enabled",
                    False,
                ),
            )
        )
        last_recovery = float(
            target_state.get("last_recovery_epoch", 0.0) or 0.0
        )
        cooldown_age = max(0.0, now - last_recovery)

        rate_limited_until = float(
            target_state.get("rate_limited_until_epoch", 0.0) or 0.0
        )
        if now < rate_limited_until:
            return {
                "chat_id": chat_id,
                "result": "RATE_LIMIT_BACKOFF",
                "contract_state": contract_state,
                "retry_after_seconds": max(0.0, rate_limited_until - now),
                "brain": brain,
            }

        if cooldown_age < cooldown_seconds:
            return {
                "chat_id": chat_id,
                "result": "COOLDOWN",
                "contract_state": contract_state,
                "cooldown_age": cooldown_age,
                "brain": brain,
            }

        bridge = self._bridge(target, common)
        opened = bridge.wake()
        if opened.get("result") != "NATIVE_EXACT_CHAT":
            return {
                "chat_id": chat_id,
                "result": str(opened.get("result")),
                "open": opened,
                "contract_state": contract_state,
                "brain": brain,
            }

        initial_xml = bridge._ui_xml()
        initial_ui = inspect_chat_ui(initial_xml, [])
        initial_stop = bool(initial_ui["stop_bounds"])
        initial_worked = worked_timer_seconds(initial_xml)
        initial_tail = response_tail_digest(initial_xml)
        initial_draft = composer_text(initial_ui)
        resume_message = str(
            target.get("resume_message") or "Continue Logres work."
        )

        if ui_rate_limited(initial_xml):
            backoff_seconds = float(
                target.get(
                    "rate_limit_backoff_seconds",
                    common.get("rate_limit_backoff_seconds", 600),
                )
            )
            target_state["rate_limited_until_epoch"] = now + backoff_seconds
            target_state["last_rate_limit_epoch"] = now
            return {
                "chat_id": chat_id,
                "result": "RATE_LIMITED",
                "contract_state": contract_state,
                "retry_after_seconds": backoff_seconds,
                "brain": brain,
            }

        if initial_draft and initial_draft != resume_message:
            return {
                "chat_id": chat_id,
                "result": "USER_DRAFT_HOLD",
                "contract_state": contract_state,
                "brain": brain,
            }

        later_xml = initial_xml
        later_ui = initial_ui
        later_stop = initial_stop
        later_worked = initial_worked
        later_tail = initial_tail
        phone_ai_result: dict | None = None

        ambiguous_running_candidate = (
            phone_ai_ambiguity_enabled
            and use_runtime_contract
            and contract_state == "RUNNING"
            and not initial_stop
            and heartbeat_age >= heartbeat_timeout
        )

        if initial_stop:
            self.sleeper(probe_seconds)
            later_xml = bridge._ui_xml()
            later_ui = inspect_chat_ui(later_xml, [])
            later_stop = bool(later_ui["stop_bounds"])
            later_worked = worked_timer_seconds(later_xml)
            later_tail = response_tail_digest(later_xml)
            action = contract_probe_action(
                contract_state=contract_state,
                initial_stop_present=initial_stop,
                initial_worked_seconds=initial_worked,
                initial_tail_digest=initial_tail,
                later_stop_present=later_stop,
                later_worked_seconds=later_worked,
                later_tail_digest=later_tail,
            )
        elif ambiguous_running_candidate:
            self.sleeper(ambiguity_probe_seconds)
            later_xml = bridge._ui_xml()
            later_ui = inspect_chat_ui(later_xml, [])
            later_stop = bool(later_ui["stop_bounds"])
            later_worked = worked_timer_seconds(later_xml)
            later_tail = response_tail_digest(later_xml)

            action = expired_running_no_stop_probe_action(
                initial_tail_digest=initial_tail,
                later_stop_present=later_stop,
                later_tail_digest=later_tail,
            )

            if action == "AMBIGUOUS":
                try:
                    phone_ai_result = self.phone_ai.classify(
                        {
                            "visible_text": visible_chat_text(
                                later_xml,
                            ),
                            "stop_present": later_stop,
                            "worked_timer_advanced": (
                                initial_worked is not None
                                and later_worked is not None
                                and later_worked > initial_worked
                            ),
                            "response_tail_changed": (
                                later_tail != initial_tail
                            ),
                            "rate_limit_banner": ui_rate_limited(
                                later_xml,
                            ),
                            "user_draft": bool(
                                composer_text(later_ui)
                            ),
                            "input_required": False,
                            "turn_ended_signal": False,
                            "turn_heartbeat_fresh": False,
                        },
                        deterministic_state="AMBIGUOUS",
                    )
                except Exception as exc:
                    phone_ai_result = {
                        "label": "UNKNOWN",
                        "queried": False,
                        "confidence": 0.0,
                        "margin": 0.0,
                        "reason": (
                            "classifier_error:"
                            f"{type(exc).__name__}"
                        ),
                    }
                phone_ai_summary = {
                    "label": str(
                        phone_ai_result.get(
                            "label",
                            "UNKNOWN",
                        )
                    ),
                    "confidence": phone_ai_result.get(
                        "confidence",
                    ),
                    "margin": phone_ai_result.get(
                        "margin",
                    ),
                    "reason": phone_ai_result.get(
                        "reason",
                    ),
                    "queried": bool(
                        phone_ai_result.get(
                            "queried",
                            False,
                        )
                    ),
                }
                target_state["last_phone_ai"] = {
                    **phone_ai_summary,
                    "epoch": now,
                }
                self.audit(
                    {
                        "chat_id": chat_id,
                        "action": "PHONE_AI_DECISION",
                        "contract_state": contract_state,
                        "heartbeat_age": heartbeat_age,
                        "phone_ai": phone_ai_summary,
                    }
                )
                action = phone_ai_recovery_action(
                    phone_ai_summary["label"],
                    stop_count=len(
                        later_ui.get(
                            "stop_bounds",
                            [],
                        )
                    ),
                )
        else:
            action = contract_probe_action(
                contract_state=contract_state,
                initial_stop_present=initial_stop,
                initial_worked_seconds=initial_worked,
                initial_tail_digest=initial_tail,
                later_stop_present=later_stop,
                later_worked_seconds=later_worked,
                later_tail_digest=later_tail,
            )

        target_state["last_checked_epoch"] = now
        target_state["last_seen_stop"] = later_stop
        target_state["last_tail_digest"] = later_tail
        target_state["last_worked_seconds"] = later_worked
        target_state["contract_state"] = contract_state

        if action == "AI_ACTIVE_HOLD":
            return {
                "chat_id": chat_id,
                "result": "PHONE_AI_ACTIVE_HOLD",
                "contract_state": contract_state,
                "phone_ai": phone_ai_result,
                "brain": brain,
            }

        if action == "AI_RATE_LIMITED":
            backoff_seconds = float(
                target.get(
                    "rate_limit_backoff_seconds",
                    common.get(
                        "rate_limit_backoff_seconds",
                        600,
                    ),
                )
            )
            target_state["rate_limited_until_epoch"] = (
                now + backoff_seconds
            )
            target_state["last_rate_limit_epoch"] = now
            return {
                "chat_id": chat_id,
                "result": "PHONE_AI_RATE_LIMITED",
                "contract_state": contract_state,
                "retry_after_seconds": backoff_seconds,
                "phone_ai": phone_ai_result,
                "brain": brain,
            }

        if action == "AI_WAITING_USER":
            return {
                "chat_id": chat_id,
                "result": "PHONE_AI_WAITING_USER",
                "contract_state": contract_state,
                "phone_ai": phone_ai_result,
                "brain": brain,
            }

        if action == "AI_HOLD":
            return {
                "chat_id": chat_id,
                "result": "PHONE_AI_HOLD",
                "contract_state": contract_state,
                "phone_ai": phone_ai_result,
                "brain": brain,
            }

        if action == "WORKING":
            if use_runtime_contract and contract_state == "RUNNING":
                self.contracts.heartbeat(
                    chat_id,
                    reason=(
                        "phone AI liveness proof"
                        if phone_ai_result is not None
                        else "native UI liveness proof"
                    ),
                )
            return {
                "chat_id": chat_id,
                "result": "WORKING",
                "contract_state": contract_state,
                "probe_seconds": (
                    ambiguity_probe_seconds
                    if phone_ai_result is not None
                    else probe_seconds
                ),
                "worked_timer_before": initial_worked,
                "worked_timer_after": later_worked,
                "phone_ai": phone_ai_result,
                "brain": brain,
            }

        stopped = False

        if action == "RESUME" and initial_draft == resume_message:
            if len(initial_ui.get("send_bounds", [])) != 1:
                return {
                    "chat_id": chat_id,
                    "result": "SYSTEM_DRAFT_WAIT",
                    "contract_state": contract_state,
                    "brain": brain,
                }
            x, y = bounds_center(initial_ui["send_bounds"][0])
            bridge.transport.shell(f"input tap {x} {y}")
            before = response_tail_digest(bridge._ui_xml())
            response = self._response_probe(
                bridge,
                before,
                float(common.get("verify_after_seconds", 8)),
            )
            target_state["last_recovery_epoch"] = now
            target_state["last_recovery_result"] = response
            if (
                use_runtime_contract
                and response in {"RESPONDING", "RESPONDED"}
            ):
                self.contracts.set_state(
                    chat_id,
                    "RUNNING",
                    reason="watchdog resumed existing system draft",
                )
            self.audit(
                {
                    "chat_id": chat_id,
                    "action": "RESUME_EXISTING_SYSTEM_DRAFT",
                    "stopped": False,
                    "result": response,
                    "contract_state": contract_state,
                    "active_tasks": brain["active_tasks"],
                }
            )
            return {
                "chat_id": chat_id,
                "result": response,
                "action": "RESUME_EXISTING_SYSTEM_DRAFT",
                "stopped": False,
                "contract_state": contract_state,
                "brain": brain,
            }

        if action == "STOP_AND_RESUME":
            if len(later_ui["stop_bounds"]) != 1:
                return {
                    "chat_id": chat_id,
                    "result": "STOP_AMBIGUOUS",
                    "ui": later_ui,
                    "contract_state": contract_state,
                    "brain": brain,
                }
            x, y = bounds_center(later_ui["stop_bounds"][0])
            bridge.transport.shell(f"input tap {x} {y}")
            stopped = True

        outcome = self._send_resume(
            bridge,
            target,
            common,
            stopped=stopped,
        )
        target_state["last_recovery_epoch"] = now
        target_state["last_recovery_result"] = outcome["result"]

        if (
            use_runtime_contract
            and outcome["result"] in {"RESPONDING", "RESPONDED"}
        ):
            self.contracts.set_state(
                chat_id,
                "RUNNING",
                reason="watchdog resumed chat",
            )

        self.audit(
            {
                "chat_id": chat_id,
                "action": action,
                "stopped": stopped,
                "result": outcome["result"],
                "contract_state": contract_state,
                "active_tasks": brain["active_tasks"],
                "probe_seconds": probe_seconds if initial_stop else 0,
                "worked_timer_before": initial_worked,
                "worked_timer_after": later_worked,
                "phone_ai": phone_ai_result,
            }
        )
        return {
            "chat_id": chat_id,
            "result": outcome["result"],
            "action": action,
            "stopped": stopped,
            "contract_state": contract_state,
            "phone_ai": phone_ai_result,
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

