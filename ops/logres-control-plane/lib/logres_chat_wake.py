from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from xml.etree import ElementTree

CHATGPT_PACKAGE = "com.openai.chatgpt"
CHATGPT_ACTIVITY = "com.openai.chatgpt/.MainActivity"
DEFAULT_ROOT = Path("/home/ubuntu/logres")
CONVERSATION_PATH = re.compile(r"^/c/[A-Za-z0-9_-]{6,160}/?$")
COMMAND_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
SAFE_MESSAGE = re.compile(r"^[A-Za-z0-9 .,!?'_:+/()#-]{1,180}$")
BOUNDS = re.compile(r"^\[(\d+),(\d+)\]\[(\d+),(\d+)\]$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_target_url(value: str) -> str:
    parsed = urlparse(str(value).strip())
    if parsed.scheme != "https":
        raise ValueError("target URL must use https")
    if parsed.hostname not in {"chatgpt.com", "chat.openai.com"}:
        raise ValueError("target URL must be a ChatGPT conversation URL")
    if not CONVERSATION_PATH.fullmatch(parsed.path):
        raise ValueError("target URL must identify one exact ChatGPT conversation")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("target URL must not contain params, query, or fragment")
    return parsed.geturl()


def parse_health(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in str(raw).splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()
    return result


def bounds_center(value: str) -> tuple[int, int]:
    match = BOUNDS.fullmatch(str(value))
    if not match:
        raise ValueError(f"invalid UI bounds: {value!r}")
    left, top, right, bottom = map(int, match.groups())
    return ((left + right) // 2, (top + bottom) // 2)


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _semantic_text(node) -> str:
    return " ".join(
        str(node.attrib.get(key) or "").strip()
        for key in ("text", "content-desc", "hint")
    ).strip()


def _is_enabled(node) -> bool:
    return node.attrib.get("enabled", "true").lower() == "true"


def _is_clickable(node) -> bool:
    return node.attrib.get("clickable", "false").lower() == "true"


def _nearest_clickable(node, parents: dict):
    current = node
    while current is not None:
        if _is_enabled(current) and _is_clickable(current) and current.attrib.get("bounds"):
            return current
        current = parents.get(current)
    return node


def inspect_chat_ui(xml_text: str, semantic_labels: list[str]) -> dict:
    root = ElementTree.fromstring(xml_text)
    parents = {child: parent for parent in root.iter() for child in parent}
    package_nodes = [
        node for node in root.iter("node")
        if node.attrib.get("package") in {"", CHATGPT_PACKAGE}
    ]
    visible_text = [_semantic_text(node) for node in package_nodes]
    visible_folded = "\n".join(x.casefold() for x in visible_text if x)
    matched_labels = [
        label for label in semantic_labels
        if str(label).strip() and str(label).strip().casefold() in visible_folded
    ]

    # The native app exposes the real composer as android.widget.EditText.
    # Do not infer a composer merely because an assistant/user message contains
    # words such as "message" or "reply"; that produced false positives in long
    # chats and could make an exact-chat recovery fail closed unnecessarily.
    editor_candidates = []
    for node in package_nodes:
        klass = node.attrib.get("class", "")
        if not _is_enabled(node):
            continue
        if klass.endswith("EditText") and node.attrib.get("bounds"):
            editor_candidates.append(node)

    stop_candidates = []
    for node in package_nodes:
        if not _is_enabled(node):
            continue
        semantics = _semantic_text(node).casefold()
        if semantics == "stop":
            target = _nearest_clickable(node, parents)
            if target.attrib.get("bounds"):
                stop_candidates.append(target)

    send_candidates = []
    for node in package_nodes:
        if not _is_enabled(node):
            continue
        semantics = _semantic_text(node).casefold()
        if semantics in {"send", "send message"} or semantics.startswith("send "):
            target = _nearest_clickable(node, parents)
            if target.attrib.get("bounds"):
                send_candidates.append(target)

    unique_send = []
    seen_bounds = set()
    for node in send_candidates:
        bounds = node.attrib.get("bounds", "")
        if bounds and bounds not in seen_bounds:
            seen_bounds.add(bounds)
            unique_send.append(node)

    return {
        "label_matches": matched_labels,
        "semantic_labels_required": bool([x for x in semantic_labels if str(x).strip()]),
        "editor_bounds": [node.attrib.get("bounds", "") for node in editor_candidates],
        "editor_text": [node.attrib.get("text", "") for node in editor_candidates],
        "send_bounds": [node.attrib.get("bounds", "") for node in unique_send],
        "stop_bounds": [
            node.attrib.get("bounds", "")
            for node in stop_candidates
            if node.attrib.get("bounds")
        ],
    }


class PhoneTransport:
    def __init__(self, root: Path):
        self.root = root
        self.phone_qa = root / "control/android-device/logres-phone-qa"
        self.phone_health = root / "bin/logres-phone-health"

    def health(self) -> str:
        proc = subprocess.run(
            [str(self.phone_health)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout or "phone health failed").strip())
        return proc.stdout

    def shell(self, command: str) -> str:
        proc = subprocess.run(
            [str(self.phone_qa), "shell", command],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if proc.returncode:
            raise RuntimeError((proc.stderr or proc.stdout or "phone shell failed").strip())
        return proc.stdout


class ChatWakeBridge:
    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        *,
        transport: PhoneTransport | None = None,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        hardware_lock_path: str | Path = "/tmp/logres-phone-hardware-qa.lock",
        bridge_lock_path: str | Path = "/tmp/logres-chatgpt-phone-bridge.lock",
    ):
        self.root = Path(root)
        self.transport = transport or PhoneTransport(self.root)
        self.clock = clock
        self.sleeper = sleeper
        self.hardware_lock_path = Path(hardware_lock_path)
        self.bridge_lock_path = Path(bridge_lock_path)
        device_dir = self.root / "control/android-device"
        self.runtime_config = Path(
            os.environ.get(
                "LOGRES_CHAT_BRIDGE_CONFIG",
                str(device_dir / "chat-bridge.json"),
            )
        )
        self.default_config = self.root / "config/chat_bridge.default.json"
        self.state_path = device_dir / "chat-bridge-state.json"
        self.audit_path = device_dir / "chat-bridge-audit.jsonl"
        self.pause_path = device_dir / "chat-bridge.paused"

    def load_config(self) -> dict:
        source = self.runtime_config if self.runtime_config.is_file() else self.default_config
        if not source.is_file():
            raise FileNotFoundError(f"chat bridge config missing: {source}")
        config = json.loads(source.read_text())
        if not isinstance(config, dict):
            raise ValueError("chat bridge config must be a JSON object")
        config["_source"] = str(source)
        return config

    def load_state(self) -> dict:
        if not self.state_path.is_file():
            return {"last_action_epoch": 0.0, "command_ids": []}
        try:
            state = json.loads(self.state_path.read_text())
        except Exception:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("last_action_epoch", 0.0)
        state.setdefault("command_ids", [])
        return state

    def save_state(self, state: dict) -> None:
        state = dict(state)
        state["command_ids"] = [str(x) for x in state.get("command_ids", [])][-256:]
        _atomic_json(self.state_path, state)

    def audit(
        self,
        action: str,
        result: str,
        *,
        config: dict,
        detail: str = "",
        command_key: str | None = None,
        command_id: str | None = None,
        health: dict | None = None,
    ) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        target_url = str(config.get("target_url") or "")
        record = {
            "ts": utc_now(),
            "action": action,
            "result": result,
            "target_name": str(config.get("target_name") or ""),
            "target_url_sha256": (
                hashlib.sha256(target_url.encode()).hexdigest()
                if target_url else None
            ),
            "command_key": command_key,
            "command_id": command_id,
            "phone_state": (health or {}).get("STATE"),
            "detail": str(detail)[:500],
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    @contextmanager
    def _lock(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        handle = os.fdopen(descriptor, "r+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def _validate_config(self, config: dict) -> dict:
        target_url = validate_target_url(str(config.get("target_url") or ""))
        labels = config.get("target_semantic_labels") or []
        if not isinstance(labels, list):
            raise ValueError("target_semantic_labels must be a list")
        labels = [str(value).strip() for value in labels if str(value).strip()]
        commands = config.get("approved_messages") or {}
        if not isinstance(commands, dict):
            raise ValueError("approved_messages must be an object")
        for key, text in commands.items():
            if not re.fullmatch(r"[A-Za-z0-9._:-]{1,80}", str(key)):
                raise ValueError(f"invalid approved message key: {key!r}")
            value = str(text)
            if "\n" in value or "\r" in value or not SAFE_MESSAGE.fullmatch(value):
                raise ValueError(f"approved message {key!r} violates safe text policy")
        return {
            **config,
            "target_url": target_url,
            "target_semantic_labels": labels,
            "approved_messages": commands,
        }

    def local_status(self) -> dict:
        try:
            config = self._validate_config(self.load_config())
            configured = True
            error = ""
        except Exception as exc:
            config = {}
            configured = False
            error = str(exc)
        return {
            "enabled": bool(config.get("enabled", False)),
            "paused": self.pause_path.exists(),
            "configured": configured,
            "target_name": str(config.get("target_name") or ""),
            "config_source": str(config.get("_source") or ""),
            "error": error,
        }

    def status(self, *, local_only: bool = False) -> dict:
        result = self.local_status()
        if local_only:
            result["mode"] = "local-only"
            return result
        try:
            result["phone"] = parse_health(self.transport.health())
        except Exception as exc:
            result["phone_error"] = str(exc)
        return result

    def pause(self) -> dict:
        self.pause_path.parent.mkdir(parents=True, exist_ok=True)
        self.pause_path.write_text(utc_now() + "\n")
        return {"result": "PAUSED"}

    def resume(self) -> dict:
        self.pause_path.unlink(missing_ok=True)
        return {"result": "RESUMED"}

    def dry_run(self, command_key: str | None = None) -> dict:
        config = self._validate_config(self.load_config())
        result = {
            "result": "DRY_RUN",
            "enabled": bool(config.get("enabled", False)),
            "paused": self.pause_path.exists(),
            "target_name": str(config.get("target_name") or ""),
            "target_url_sha256": hashlib.sha256(
                config["target_url"].encode()
            ).hexdigest(),
            "native_package": CHATGPT_PACKAGE,
            "transport": "existing-logres-phone-qa",
        }
        if command_key is not None:
            if command_key not in config["approved_messages"]:
                raise ValueError("command key is not approved")
            result["command_key"] = command_key
            result["message"] = config["approved_messages"][command_key]
        return result

    def _preflight(
        self,
        config: dict,
        state: dict,
        *,
        command_id: str | None = None,
    ) -> tuple[str, dict]:
        if not config.get("enabled", False):
            return "DISABLED", {}
        if self.pause_path.exists():
            return "PAUSED", {}
        if command_id and command_id in state.get("command_ids", []):
            return "DUPLICATE", {}
        interval = max(0, int(config.get("min_interval_seconds", 300)))
        if self.clock() - float(state.get("last_action_epoch", 0.0)) < interval:
            return "RATE_LIMITED", {}
        health = parse_health(self.transport.health())
        phone_state = health.get("STATE", "UNKNOWN")
        if phone_state in {"NO_ADB", "THERMAL_BLOCK"}:
            return f"DEFERRED_{phone_state}", health
        if phone_state == "POWER_BLOCK":
            if not config.get(
                "allow_low_battery_wake",
                False,
            ):
                return "DEFERRED_POWER_BLOCK", health

            try:
                battery_level = int(
                    health.get(
                        "BATTERY_LEVEL",
                        "",
                    )
                )
                hard_floor = int(
                    config.get(
                        "low_battery_wake_floor_percent",
                        10,
                    )
                )
            except (TypeError, ValueError):
                return "DEFERRED_POWER_BLOCK", health

            hard_floor = max(
                0,
                min(
                    100,
                    hard_floor,
                ),
            )
            if battery_level < hard_floor:
                return "DEFERRED_CRITICAL_BATTERY", health
        return "READY", health

    def _ui_xml(self) -> str:
        return self.transport.shell(
            "uiautomator dump /sdcard/logres-chat-bridge.xml >/dev/null 2>&1; "
            "cat /sdcard/logres-chat-bridge.xml"
        )

    def _semantic_ui(self, config: dict) -> dict:
        return inspect_chat_ui(
            self._ui_xml(),
            list(config.get("target_semantic_labels") or []),
        )

    def _verify_exact_chat(self, config: dict) -> tuple[bool, dict]:
        ui = self._semantic_ui(config)
        labels_required = ui["semantic_labels_required"]
        labels_ok = bool(ui["label_matches"]) if labels_required else True
        editor_ok = len(ui["editor_bounds"]) == 1
        return labels_ok and editor_ok, ui

    def _foreground(self) -> str:
        return self.transport.shell(
            "dumpsys activity activities | "
            "grep -m1 -E 'topResumedActivity=|mResumedActivity=' || true"
        ).strip()

    def _open_exact_native_chat(self, config: dict) -> tuple[str, dict]:
        target_url = config["target_url"]
        self.transport.shell(f"pm enable {CHATGPT_PACKAGE} >/dev/null 2>&1 || true")
        self.transport.shell("input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true")
        self.transport.shell(
            "am start -W -a android.intent.action.VIEW "
            f"-d {shlex.quote(target_url)} -n {CHATGPT_ACTIVITY}"
        )
        self.sleeper(float(config.get("settle_seconds", 0.8)))
        foreground = self._foreground()
        if CHATGPT_PACKAGE not in foreground:
            return "NATIVE_FOREGROUND_FAILED", {"foreground": foreground}
        exact, ui = self._verify_exact_chat(config)
        if not exact:
            return "SEMANTIC_TARGET_VERIFY_FAILED", {
                "foreground": foreground,
                "ui": ui,
            }
        return "NATIVE_EXACT_CHAT", {"foreground": foreground, "ui": ui}

    def wake(self) -> dict:
        config = self._validate_config(self.load_config())
        state = self.load_state()
        try:
            with self._lock(self.bridge_lock_path):
                try:
                    with self._lock(self.hardware_lock_path):
                        result, health = self._preflight(config, state)
                        if result != "READY":
                            self.audit("wake", result, config=config, health=health)
                            return {"result": result, "health": health}
                        result, detail = self._open_exact_native_chat(config)
                        if result == "NATIVE_EXACT_CHAT":
                            state["last_action_epoch"] = self.clock()
                            state["last_result"] = result
                            self.save_state(state)
                        self.audit(
                            "wake",
                            result,
                            config=config,
                            health=health,
                            detail=json.dumps(detail, sort_keys=True),
                        )
                        return {"result": result, "health": health, **detail}
                except BlockingIOError:
                    self.audit("wake", "DEFERRED_QA_BUSY", config=config)
                    return {"result": "DEFERRED_QA_BUSY"}
        except BlockingIOError:
            return {"result": "BUSY"}

    def _input_text(self, value: str) -> None:
        encoded = value.replace("%", "%25").replace(" ", "%s").replace("&", "\\&")
        self.transport.shell(f"input text {shlex.quote(encoded)}")

    def _send_allowlisted(self, config: dict, text: str) -> dict:
        ui = self._semantic_ui(config)
        if len(ui["editor_bounds"]) != 1:
            raise RuntimeError(
                f"expected exactly one semantic composer; found {len(ui['editor_bounds'])}"
            )
        if str(ui["editor_text"][0]).strip():
            raise RuntimeError("composer has an existing draft; refusing to overwrite")
        editor_x, editor_y = bounds_center(ui["editor_bounds"][0])
        self.transport.shell(f"input tap {editor_x} {editor_y}")
        self._input_text(text)
        self.sleeper(0.2)

        ui = self._semantic_ui(config)
        if len(ui["send_bounds"]) != 1:
            raise RuntimeError(
                f"expected exactly one semantic Send control; found {len(ui['send_bounds'])}"
            )
        send_x, send_y = bounds_center(ui["send_bounds"][0])
        self.transport.shell(f"input tap {send_x} {send_y}")
        return {
            "composer_bounds": ui["editor_bounds"][0],
            "send_bounds": ui["send_bounds"][0],
        }

    def send(self, command_key: str, command_id: str) -> dict:
        config = self._validate_config(self.load_config())
        if command_key not in config["approved_messages"]:
            raise ValueError("command key is not approved")
        if not COMMAND_ID.fullmatch(command_id):
            raise ValueError("invalid command id")
        message = str(config["approved_messages"][command_key])
        state = self.load_state()

        try:
            with self._lock(self.bridge_lock_path):
                try:
                    with self._lock(self.hardware_lock_path):
                        result, health = self._preflight(
                            config, state, command_id=command_id
                        )
                        if result != "READY":
                            self.audit(
                                "send",
                                result,
                                config=config,
                                command_key=command_key,
                                command_id=command_id,
                                health=health,
                            )
                            return {"result": result, "health": health}

                        result, detail = self._open_exact_native_chat(config)
                        if result != "NATIVE_EXACT_CHAT":
                            self.audit(
                                "send",
                                result,
                                config=config,
                                command_key=command_key,
                                command_id=command_id,
                                health=health,
                                detail=json.dumps(detail, sort_keys=True),
                            )
                            return {"result": result, **detail}

                        send_detail = self._send_allowlisted(config, message)
                        state["last_action_epoch"] = self.clock()
                        state["last_result"] = "SENT"
                        state["command_ids"] = [
                            *state.get("command_ids", []),
                            command_id,
                        ][-256:]
                        self.save_state(state)
                        self.audit(
                            "send",
                            "SENT",
                            config=config,
                            command_key=command_key,
                            command_id=command_id,
                            health=health,
                            detail=json.dumps(send_detail, sort_keys=True),
                        )
                        return {
                            "result": "SENT",
                            "command_key": command_key,
                            "command_id": command_id,
                            **send_detail,
                        }
                except BlockingIOError:
                    self.audit(
                        "send",
                        "DEFERRED_QA_BUSY",
                        config=config,
                        command_key=command_key,
                        command_id=command_id,
                    )
                    return {"result": "DEFERRED_QA_BUSY"}
        except BlockingIOError:
            return {"result": "BUSY"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="logres-chat-wake",
        description="Guarded native ChatGPT exact-chat wake bridge for Logres.",
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("LOGRES_ROOT", str(DEFAULT_ROOT)),
    )
    sub = parser.add_subparsers(dest="action", required=True)

    status = sub.add_parser("status")
    status.add_argument("--local-only", action="store_true")
    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("wake")

    dry = sub.add_parser("dry-run")
    dry.add_argument("command_key", nargs="?")

    send = sub.add_parser("send")
    send.add_argument("command_key")
    send.add_argument("--command-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bridge = ChatWakeBridge(args.root)
    if args.action == "status":
        result = bridge.status(local_only=args.local_only)
    elif args.action == "pause":
        result = bridge.pause()
    elif args.action == "resume":
        result = bridge.resume()
    elif args.action == "dry-run":
        result = bridge.dry_run(args.command_key)
    elif args.action == "wake":
        result = bridge.wake()
    else:
        result = bridge.send(args.command_key, args.command_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if not str(result.get("result", "")).endswith("FAILED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
