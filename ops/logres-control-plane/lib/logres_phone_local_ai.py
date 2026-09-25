from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("/home/ubuntu/logres")
LABELS = (
    "ACTIVE",
    "ENDED",
    "STUCK",
    "RATE_LIMITED",
    "WAITING_USER",
    "UNKNOWN",
)
LABEL_SET = frozenset(LABELS)
WORD_RE = re.compile(r"[a-z0-9_]+")
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
TOKEN_RE = re.compile(
    r"\b(ACTIVE|ENDED|STUCK|RATE_LIMITED|WAITING_USER|UNKNOWN)\b"
)

TRAINING_CASES: tuple[dict[str, Any], ...] = (
    # ACTIVE
    {"label": "ACTIVE", "text": "Stop button visible and Worked for timer advanced during probe.", "stop_present": True, "worked_timer_advanced": True},
    {"label": "ACTIVE", "text": "Assistant response tail changed while generation control remained visible.", "stop_present": True, "response_tail_changed": True},
    {"label": "ACTIVE", "text": "New tool output appeared and the running turn heartbeat is fresh.", "tool_output_changed": True, "turn_heartbeat_fresh": True},
    {"label": "ACTIVE", "text": "Generation is still moving and response content keeps growing.", "response_tail_changed": True},
    {"label": "ACTIVE", "text": "Worked for counter increased from one snapshot to the next.", "stop_present": True, "worked_timer_advanced": True},
    {"label": "ACTIVE", "text": "The assistant is actively producing new output.", "tool_output_changed": True},
    {"label": "ACTIVE", "text": "Visible response progress was observed during the liveness probe.", "response_tail_changed": True},
    {"label": "ACTIVE", "text": "Tool execution is ongoing and the turn lease is fresh.", "turn_heartbeat_fresh": True, "tool_output_changed": True},

    # ENDED
    {"label": "ENDED", "text": "Stop control disappeared after the answer completed.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "The response turn ended normally and continuation is appropriate.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "Completed answer visible with no Stop control and no user draft.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "Copy and Read aloud controls are visible after generation finished.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "Previous assistant turn is complete and the continuation contract is ready.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "Generation finished normally; there is no active response control.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "The turn closed cleanly and the composer is empty.", "turn_ended_signal": True},
    {"label": "ENDED", "text": "No active generation remains after the completed response.", "turn_ended_signal": True},

    # STUCK
    {"label": "STUCK", "text": "Stop button remains visible but Worked for timer and response tail are frozen.", "stop_present": True},
    {"label": "STUCK", "text": "Generation control is present but no progress occurred during the probe.", "stop_present": True},
    {"label": "STUCK", "text": "Worked for timer did not advance and the Stop control is still visible.", "stop_present": True},
    {"label": "STUCK", "text": "Assistant response tail stayed unchanged while Stop remained on screen.", "stop_present": True},
    {"label": "STUCK", "text": "Stop control is stuck for the full liveness window.", "stop_present": True},
    {"label": "STUCK", "text": "Generation appears active but nothing changes between snapshots.", "stop_present": True},
    {"label": "STUCK", "text": "Stop is visible and no new tool or response output appeared.", "stop_present": True},
    {"label": "STUCK", "text": "The response stalled with the native Stop action still present.", "stop_present": True},

    # RATE_LIMITED
    {"label": "RATE_LIMITED", "text": "Too many requests. Try again later.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "You have reached a request limit.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "Rate limit exceeded for this request.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "Request rejected because too many requests were sent.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "You are sending requests too quickly.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "Usage cap reached, please retry later.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "ChatGPT is temporarily rate limited.", "rate_limit_banner": True},
    {"label": "RATE_LIMITED", "text": "Please wait before sending another request.", "rate_limit_banner": True},

    # WAITING_USER
    {"label": "WAITING_USER", "text": "The message composer contains unsent user text.", "user_draft": True},
    {"label": "WAITING_USER", "text": "A user-owned draft is present in the composer.", "user_draft": True},
    {"label": "WAITING_USER", "text": "The flow is waiting for user input.", "input_required": True},
    {"label": "WAITING_USER", "text": "User confirmation is required before continuing.", "input_required": True},
    {"label": "WAITING_USER", "text": "A follow-up question needs the user to answer.", "input_required": True},
    {"label": "WAITING_USER", "text": "The composer already has text that the watchdog did not create.", "user_draft": True},
    {"label": "WAITING_USER", "text": "The assistant explicitly asks for a user decision.", "input_required": True},
    {"label": "WAITING_USER", "text": "Waiting on manual approval from the user.", "input_required": True},

    # UNKNOWN
    {"label": "UNKNOWN", "text": "Stop is absent but the turn heartbeat is fresh and tool work may still be running.", "turn_heartbeat_fresh": True},
    {"label": "UNKNOWN", "text": "Signals conflict and the current ChatGPT state is ambiguous."},
    {"label": "UNKNOWN", "text": "The native UI is only partially loaded and state cannot be determined."},
    {"label": "UNKNOWN", "text": "The phone changed screens unexpectedly and evidence is incomplete."},
    {"label": "UNKNOWN", "text": "There is insufficient evidence to decide whether the response ended."},
    {"label": "UNKNOWN", "text": "Stop control is missing while background tool execution might still be active.", "turn_heartbeat_fresh": True},
    {"label": "UNKNOWN", "text": "Unknown native UI state with conflicting liveness signals."},
    {"label": "UNKNOWN", "text": "Timer and response signals disagree, so recovery state is uncertain."},
)


def parse_label(text: str) -> str:
    cleaned = ANSI_RE.sub("", str(text or "")).upper()
    matches = TOKEN_RE.findall(cleaned)
    unique = set(matches)
    if len(unique) != 1:
        return "UNKNOWN"
    return next(iter(unique))


def should_query_local_ai(deterministic_state: str) -> bool:
    return str(deterministic_state or "").strip().upper() == "AMBIGUOUS"


def _flag(observation: dict[str, Any], key: str) -> bool:
    return bool(observation.get(key))


def observation_text(observation: dict[str, Any]) -> str:
    text_fields = (
        "visible_text",
        "ui_text",
        "error_text",
        "status_text",
        "assistant_text",
        "composer_text",
        "text",
    )
    pieces = [
        str(observation.get(key) or "").strip()
        for key in text_fields
        if str(observation.get(key) or "").strip()
    ]
    flags = {
        "stop": _flag(observation, "stop_present"),
        "progress": (
            _flag(observation, "worked_timer_advanced")
            or _flag(observation, "response_tail_changed")
            or _flag(observation, "tool_output_changed")
        ),
        "rate": _flag(observation, "rate_limit_banner"),
        "draft": _flag(observation, "user_draft"),
        "input": _flag(observation, "input_required"),
        "ended": _flag(observation, "turn_ended_signal"),
        "heartbeat": _flag(observation, "turn_heartbeat_fresh"),
    }
    pieces.extend(
        f"flag_{name}_{1 if value else 0}"
        for name, value in flags.items()
    )
    return " ".join(pieces).strip().lower()


def _features(text: str) -> Counter[str]:
    normalized = " ".join(str(text or "").lower().split())
    words = WORD_RE.findall(normalized)
    counts: Counter[str] = Counter()
    for word in words:
        counts[f"w:{word}"] += 1
    for first, second in zip(words, words[1:]):
        counts[f"b:{first}_{second}"] += 1
    return counts


def _case_observation(case: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in case.items()
        if key != "label"
    }


def _train_model() -> dict[str, Any]:
    class_docs: Counter[str] = Counter()
    class_feature_counts: dict[str, Counter[str]] = {
        label: Counter()
        for label in LABELS
    }
    class_feature_totals: Counter[str] = Counter()
    vocabulary: set[str] = set()

    for case in TRAINING_CASES:
        label = str(case["label"])
        feats = _features(
            observation_text(
                _case_observation(case),
            )
        )
        class_docs[label] += 1
        class_feature_counts[label].update(feats)
        class_feature_totals[label] += sum(feats.values())
        vocabulary.update(feats)

    return {
        "class_docs": dict(class_docs),
        "class_feature_counts": {
            label: dict(counts)
            for label, counts in class_feature_counts.items()
        },
        "class_feature_totals": dict(class_feature_totals),
        "vocabulary": sorted(vocabulary),
        "total_docs": sum(class_docs.values()),
    }


_PRECOMPUTED_MODEL = _train_model()


def _classify_with_model(
    observation: dict[str, Any],
    model: dict[str, Any],
    *,
    min_confidence: float,
    min_margin: float,
) -> dict[str, Any]:
    target = _features(
        observation_text(observation),
    )

    base_vocabulary = set(
        model["vocabulary"],
    )
    unseen = sum(
        feature not in base_vocabulary
        for feature in target
    )
    vocab_size = max(
        1,
        len(base_vocabulary) + unseen,
    )
    total_docs = int(model["total_docs"])
    alpha = 1.0

    scores: dict[str, float] = {}
    for label in LABELS:
        class_docs = int(
            model["class_docs"].get(label, 0)
        )
        prior = math.log(
            (class_docs + alpha)
            / (total_docs + alpha * len(LABELS))
        )
        denominator = (
            int(
                model["class_feature_totals"].get(
                    label,
                    0,
                )
            )
            + alpha * vocab_size
        )
        feature_counts = (
            model["class_feature_counts"].get(
                label,
                {},
            )
        )
        score = prior
        for feature, count in target.items():
            probability = (
                int(feature_counts.get(feature, 0))
                + alpha
            ) / denominator
            score += count * math.log(probability)
        scores[label] = score

    maximum = max(scores.values())
    exp_scores = {
        label: math.exp(score - maximum)
        for label, score in scores.items()
    }
    total = sum(exp_scores.values()) or 1.0
    probabilities = {
        label: value / total
        for label, value in exp_scores.items()
    }
    ranked = sorted(
        probabilities.items(),
        key=lambda item: item[1],
        reverse=True,
    )
    top_label, confidence = ranked[0]
    second_confidence = (
        ranked[1][1]
        if len(ranked) > 1
        else 0.0
    )
    margin = confidence - second_confidence

    label = top_label
    reason = "classified"
    if (
        confidence < float(min_confidence)
        or margin < float(min_margin)
    ):
        label = "UNKNOWN"
        reason = "low_confidence"

    return {
        "label": label,
        "raw_label": top_label,
        "confidence": round(confidence, 6),
        "margin": round(margin, 6),
        "reason": reason,
    }


def classify_statistical(
    observation: dict[str, Any],
    *,
    min_confidence: float = 0.64,
    min_margin: float = 0.10,
) -> dict[str, Any]:
    return _classify_with_model(
        observation,
        _PRECOMPUTED_MODEL,
        min_confidence=min_confidence,
        min_margin=min_margin,
    )


def safety_decision(
    *,
    mem_available_kb: int | None,
    battery_temp_millic: int | None,
    min_mem_available_mb: int,
    max_battery_temp_c: float,
) -> tuple[bool, str]:
    if mem_available_kb is None or battery_temp_millic is None:
        return False, "sensor_unavailable"
    if mem_available_kb < int(min_mem_available_mb) * 1024:
        return False, "low_memory"
    if battery_temp_millic > int(float(max_battery_temp_c) * 1000):
        return False, "battery_hot"
    return True, "ok"


def _runner_source() -> str:
    model_json = json.dumps(
        _PRECOMPUTED_MODEL,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return f'''import base64, json, math, re, sys
from collections import Counter

LABELS={LABELS!r}
WORD_RE=re.compile(r"[a-z0-9_]+")
MODEL=json.loads({model_json!r})

def obs_text(o):
    fields=("visible_text","ui_text","error_text","status_text","assistant_text","composer_text","text")
    pieces=[str(o.get(k) or "").strip() for k in fields if str(o.get(k) or "").strip()]
    flags={{
        "stop":bool(o.get("stop_present")),
        "progress":bool(o.get("worked_timer_advanced") or o.get("response_tail_changed") or o.get("tool_output_changed")),
        "rate":bool(o.get("rate_limit_banner")),
        "draft":bool(o.get("user_draft")),
        "input":bool(o.get("input_required")),
        "ended":bool(o.get("turn_ended_signal")),
        "heartbeat":bool(o.get("turn_heartbeat_fresh")),
    }}
    pieces.extend("flag_%s_%d"%(k,1 if v else 0) for k,v in flags.items())
    return " ".join(pieces).strip().lower()

def features(text):
    normalized=" ".join(str(text or "").lower().split())
    words=WORD_RE.findall(normalized)
    counts=Counter()
    for word in words:
        counts["w:"+word]+=1
    for a,b in zip(words,words[1:]):
        counts["b:"+a+"_"+b]+=1
    return counts

def classify(observation,min_confidence,min_margin):
    target=features(obs_text(observation))
    base_vocab=set(MODEL["vocabulary"])
    unseen=sum(feature not in base_vocab for feature in target)
    vocab_size=max(1,len(base_vocab)+unseen)
    total_docs=int(MODEL["total_docs"])
    alpha=1.0
    scores={{}}
    for label in LABELS:
        docs=int(MODEL["class_docs"].get(label,0))
        score=math.log((docs+alpha)/(total_docs+alpha*len(LABELS)))
        denominator=int(MODEL["class_feature_totals"].get(label,0))+alpha*vocab_size
        counts=MODEL["class_feature_counts"].get(label,{{}})
        for feature,count in target.items():
            probability=(int(counts.get(feature,0))+alpha)/denominator
            score+=count*math.log(probability)
        scores[label]=score
    maximum=max(scores.values())
    ex={{label:math.exp(score-maximum) for label,score in scores.items()}}
    total=sum(ex.values()) or 1.0
    probs={{label:value/total for label,value in ex.items()}}
    ranked=sorted(probs.items(),key=lambda item:item[1],reverse=True)
    raw,confidence=ranked[0]
    second=ranked[1][1] if len(ranked)>1 else 0.0
    margin=confidence-second
    label=raw
    reason="classified"
    if confidence<float(min_confidence) or margin<float(min_margin):
        label="UNKNOWN"
        reason="low_confidence"
    return {{"label":label,"raw_label":raw,"confidence":round(confidence,6),"margin":round(margin,6),"reason":reason}}

payload=json.loads(base64.b64decode(sys.argv[1]).decode("utf-8"))
result=classify(payload["observation"],payload["min_confidence"],payload["min_margin"])
if len(sys.argv)>2:
    result["mem_available_kb"]=int(sys.argv[2])
if len(sys.argv)>3:
    result["battery_temp_millic"]=int(sys.argv[3])
result["executed"]=True
print(json.dumps(result,sort_keys=True))
'''



class TermuxSSHTransport:
    def __init__(self, config: dict[str, Any]):
        ssh = dict(config.get("ssh") or {})
        self.host = str(ssh.get("host") or "127.0.0.1")
        self.port = int(ssh.get("port") or 22023)
        self.user = str(ssh.get("user") or "")
        self.key_path = str(ssh.get("key_path") or "")
        self.control_path = str(
            ssh.get("control_path")
            or "/tmp/logres-termux-%C"
        )
        self.control_persist_seconds = int(
            ssh.get("control_persist_seconds")
            or 600
        )

    def _argv(self, remote_command: str) -> list[str]:
        if not self.user or not self.key_path:
            raise RuntimeError(
                "Termux SSH user/key are not configured"
            )
        return [
            "ssh",
            "-p",
            str(self.port),
            "-i",
            self.key_path,
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "ControlMaster=auto",
            "-o",
            f"ControlPersist={max(30, self.control_persist_seconds)}",
            "-o",
            f"ControlPath={self.control_path}",
            f"{self.user}@{self.host}",
            remote_command,
        ]

    def run(
        self,
        remote_command: str,
        *,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self._argv(remote_command),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )


class PhoneLocalAI:
    def __init__(
        self,
        root: str | Path = DEFAULT_ROOT,
        *,
        transport: TermuxSSHTransport | None = None,
    ):
        self.root = Path(root)
        device_dir = self.root / "control/android-device"
        self.runtime_config = Path(
            os.environ.get(
                "LOGRES_PHONE_LOCAL_AI_CONFIG",
                str(device_dir / "phone-local-ai.json"),
            )
        )
        self.default_config = (
            self.root / "config/phone_local_ai.default.json"
        )
        self._transport = transport

    def load_config(self) -> dict[str, Any]:
        source = (
            self.runtime_config
            if self.runtime_config.is_file()
            else self.default_config
        )
        if not source.is_file():
            return {
                "enabled": False,
                "_source": str(source),
            }
        value = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(
                "phone local AI config must be a JSON object"
            )
        value["_source"] = str(source)
        return value

    def transport(
        self,
        config: dict[str, Any],
    ) -> TermuxSSHTransport:
        return self._transport or TermuxSSHTransport(config)

    def _sensors(
        self,
        config: dict[str, Any],
    ) -> tuple[int | None, int | None, str]:
        command = r'''set -eu
mem="$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo)"
cache="$HOME/.cache/logres/battery-temp-path"
temp_path=""
[ -r "$cache" ] && IFS= read -r temp_path < "$cache" || true
if [ -z "$temp_path" ] || [ ! -r "$temp_path" ]; then
  for zone in /sys/class/thermal/thermal_zone*; do
    [ -r "$zone/type" ] && [ -r "$zone/temp" ] || continue
    IFS= read -r kind < "$zone/type" || continue
    [ "$kind" = "battery" ] || continue
    temp_path="$zone/temp"
    mkdir -p "$(dirname "$cache")"
    printf '%s\n' "$temp_path" > "$cache"
    break
  done
fi
temp=""
[ -n "$temp_path" ] && IFS= read -r temp < "$temp_path" || true
printf '%s %s\n' "$mem" "$temp"
'''
        try:
            proc = self.transport(config).run(
                command,
                timeout=10,
            )
        except Exception as exc:
            return None, None, f"{type(exc).__name__}: {exc}"
        if proc.returncode:
            return (
                None,
                None,
                (proc.stderr or proc.stdout).strip(),
            )
        parts = proc.stdout.strip().split()
        if len(parts) != 2:
            return None, None, "sensor_parse_failed"
        try:
            return int(parts[0]), int(parts[1]), ""
        except ValueError:
            return None, None, "sensor_parse_failed"

    def _python_ready(
        self,
        config: dict[str, Any],
    ) -> tuple[bool, str]:
        try:
            proc = self.transport(config).run(
                "command -v python >/dev/null 2>&1",
                timeout=8,
            )
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
        if proc.returncode:
            return False, "termux_python_unavailable"
        return True, "ok"

    def _ensure_runner(
        self,
        config: dict[str, Any],
    ) -> tuple[bool, str]:
        classifier = dict(config.get("classifier") or {})
        path = str(
            classifier.get("runner_path")
            or "/data/data/com.termux/files/home/.cache/logres/phone-local-classifier.py"
        )
        source = _runner_source().encode("utf-8")
        digest = hashlib.sha256(source).hexdigest()
        encoded = base64.b64encode(source).decode("ascii")
        command = (
            "mkdir -p $HOME/.cache/logres; "
            f"path={shlex.quote(path)}; "
            f"expected={shlex.quote(digest)}; "
            'current=""; '
            '[ -f "$path.sha256" ] && current=$(cat "$path.sha256" 2>/dev/null || true); '
            'if [ "$current" != "$expected" ] || [ ! -s "$path" ]; then '
            f"printf %s {shlex.quote(encoded)} | base64 -d > \"$path\"; "
            'chmod 600 "$path"; '
            'printf "%s\\n" "$expected" > "$path.sha256"; '
            "fi"
        )
        try:
            proc = self.transport(config).run(
                command,
                timeout=12,
            )
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"
        if proc.returncode:
            return (
                False,
                (proc.stderr or proc.stdout or "runner_install_failed").strip(),
            )
        return True, "ok"

    def _infer(
        self,
        config: dict[str, Any],
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        classifier = dict(config.get("classifier") or {})
        path = str(
            classifier.get("runner_path")
            or "/data/data/com.termux/files/home/.cache/logres/phone-local-classifier.py"
        )
        min_confidence = float(
            classifier.get("min_confidence") or 0.64
        )
        min_margin = float(
            classifier.get("min_margin") or 0.10
        )
        timeout_seconds = float(
            classifier.get("timeout_seconds") or 5
        )
        payload = {
            "observation": observation,
            "min_confidence": min_confidence,
            "min_margin": min_margin,
        }
        encoded = base64.b64encode(
            json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).decode("ascii")
        command = (
            f"python {shlex.quote(path)} "
            f"{shlex.quote(encoded)}"
        )
        try:
            proc = self.transport(config).run(
                command,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "timeout",
            }
        except Exception as exc:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        if proc.returncode:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": (
                    proc.stderr
                    or proc.stdout
                    or "classifier_failed"
                ).strip()[-500:],
            }
        try:
            value = json.loads(proc.stdout)
        except Exception:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "malformed_classifier_json",
            }
        if not isinstance(value, dict):
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "malformed_classifier_json",
            }
        label = str(value.get("label") or "UNKNOWN").upper()
        if label not in LABEL_SET:
            label = "UNKNOWN"
            value["reason"] = "invalid_classifier_label"
        value["label"] = label
        return value

    def _classify_remote_once(
        self,
        config: dict[str, Any],
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        classifier = dict(config.get("classifier") or {})
        safety = dict(config.get("safety") or {})

        path = str(
            classifier.get("runner_path")
            or "/data/data/com.termux/files/home/.cache/logres/phone-local-classifier.py"
        )
        min_confidence = float(
            classifier.get("min_confidence") or 0.64
        )
        min_margin = float(
            classifier.get("min_margin") or 0.10
        )
        timeout_seconds = float(
            classifier.get("timeout_seconds") or 5
        )
        min_mem_kb = int(
            safety.get("min_mem_available_mb") or 700
        ) * 1024
        max_temp_millic = int(
            float(
                safety.get("max_battery_temp_c") or 42.0
            ) * 1000
        )

        source = _runner_source().encode("utf-8")
        digest = hashlib.sha256(source).hexdigest()
        payload_b64 = base64.b64encode(
            json.dumps(
                {
                    "observation": observation,
                    "min_confidence": min_confidence,
                    "min_margin": min_margin,
                },
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        ).decode("ascii")

        path_q = shlex.quote(path)
        digest_q = shlex.quote(digest)
        payload_q = shlex.quote(payload_b64)

        # One SSH transaction: sensors -> safety -> runner cache -> classify.
        command = (
            "set -eu; "
            "mem=$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo); "
            'cache="$HOME/.cache/logres/battery-temp-path"; '
            'temp_path=""; '
            '[ -r "$cache" ] && IFS= read -r temp_path < "$cache" || true; '
            'if [ -z "$temp_path" ] || [ ! -r "$temp_path" ]; then '
            'for zone in /sys/class/thermal/thermal_zone*; do '
            '[ -r "$zone/type" ] && [ -r "$zone/temp" ] || continue; '
            'IFS= read -r kind < "$zone/type" || continue; '
            '[ "$kind" = "battery" ] || continue; '
            'temp_path="$zone/temp"; '
            'mkdir -p "$(dirname "$cache")"; '
            'printf "%s\\n" "$temp_path" > "$cache"; break; done; fi; '
            'temp=""; '
            '[ -n "$temp_path" ] && IFS= read -r temp < "$temp_path" || true; '
            'if [ -z "$mem" ] || [ -z "$temp" ]; then '
            "printf '%s\\n' "
            "'{\"label\":\"UNKNOWN\",\"raw_label\":\"UNKNOWN\","
            "\"confidence\":0.0,\"margin\":0.0,"
            "\"reason\":\"sensor_unavailable\",\"executed\":false}'; "
            "exit 0; fi; "
            f"if [ \"$mem\" -lt {min_mem_kb} ]; then "
            "printf '{\"label\":\"UNKNOWN\",\"raw_label\":\"UNKNOWN\","
            "\"confidence\":0.0,\"margin\":0.0,\"reason\":\"low_memory\","
            "\"executed\":false,\"mem_available_kb\":%s,"
            "\"battery_temp_millic\":%s}\\n' \"$mem\" \"$temp\"; "
            "exit 0; fi; "
            f"if [ \"$temp\" -gt {max_temp_millic} ]; then "
            "printf '{\"label\":\"UNKNOWN\",\"raw_label\":\"UNKNOWN\","
            "\"confidence\":0.0,\"margin\":0.0,\"reason\":\"battery_hot\","
            "\"executed\":false,\"mem_available_kb\":%s,"
            "\"battery_temp_millic\":%s}\\n' \"$mem\" \"$temp\"; "
            "exit 0; fi; "
            "if ! command -v python >/dev/null 2>&1; then "
            "printf '{\"label\":\"UNKNOWN\",\"raw_label\":\"UNKNOWN\","
            "\"confidence\":0.0,\"margin\":0.0,"
            "\"reason\":\"termux_python_unavailable\",\"executed\":false,"
            "\"mem_available_kb\":%s,\"battery_temp_millic\":%s}\\n' "
            "\"$mem\" \"$temp\"; exit 0; fi; "
            "mkdir -p /data/data/com.termux/files/home/.cache/logres; "
            f"path={path_q}; expected={digest_q}; "
            'current=""; '
            '[ -f "$path.sha256" ] '
            '&& current=$(cat "$path.sha256" 2>/dev/null || true); '
            'if [ "$current" != "$expected" ] || [ ! -s "$path" ]; then '
            "printf '{\"label\":\"UNKNOWN\",\"raw_label\":\"UNKNOWN\","
            "\"confidence\":0.0,\"margin\":0.0,\"reason\":\"runner_stale\","
            "\"executed\":false,\"mem_available_kb\":%s,"
            "\"battery_temp_millic\":%s}\\n' \"$mem\" \"$temp\"; "
            "exit 0; fi; "
            f"python \"$path\" {payload_q} \"$mem\" \"$temp\""
        )

        try:
            proc = self.transport(config).run(
                command,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "timeout",
                "executed": False,
            }
        except Exception as exc:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": f"{type(exc).__name__}: {exc}",
                "executed": False,
            }

        if proc.returncode:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": (
                    proc.stderr
                    or proc.stdout
                    or "classifier_failed"
                ).strip()[-500:],
                "executed": False,
            }

        try:
            value = json.loads(proc.stdout)
        except Exception:
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "malformed_classifier_json",
                "executed": False,
            }

        if not isinstance(value, dict):
            return {
                "label": "UNKNOWN",
                "raw_label": "UNKNOWN",
                "confidence": 0.0,
                "margin": 0.0,
                "reason": "malformed_classifier_json",
                "executed": False,
            }

        label = str(
            value.get("label") or "UNKNOWN"
        ).upper()
        if label not in LABEL_SET:
            label = "UNKNOWN"
            value["reason"] = "invalid_classifier_label"
        value["label"] = label
        return value

    def classify(
        self,
        observation: dict[str, Any],
        *,
        deterministic_state: str,
    ) -> dict[str, Any]:
        config = self.load_config()
        result: dict[str, Any] = {
            "label": "UNKNOWN",
            "queried": False,
            "deterministic_state": str(
                deterministic_state or ""
            ).upper(),
            "source": config.get("_source"),
        }

        if not should_query_local_ai(deterministic_state):
            result["reason"] = "deterministic_authority"
            return result
        if not bool(config.get("enabled", False)):
            result["reason"] = "disabled"
            return result

        encoded = json.dumps(
            observation,
            sort_keys=True,
            ensure_ascii=True,
        )
        if len(encoded) > int(
            config.get("max_observation_chars") or 4000
        ):
            result["reason"] = "observation_too_large"
            return result

        value = self._classify_remote_once(
            config,
            observation,
        )

        if value.get("reason") == "runner_stale":
            installed, install_reason = self._ensure_runner(
                config,
            )
            if not installed:
                result.update({
                    "reason": install_reason,
                    "runner_reason": install_reason,
                })
                return result
            value = self._classify_remote_once(
                config,
                observation,
            )
            value["runner_reason"] = "installed"
        else:
            value.setdefault(
                "runner_reason",
                "cached",
            )

        result.update(value)
        result["queried"] = bool(
            value.get("executed", False)
        )
        return result

    def status(self) -> dict[str, Any]:
        config = self.load_config()
        result = {
            "enabled": bool(config.get("enabled", False)),
            "source": config.get("_source"),
            "labels": list(LABELS),
            "backend": "termux-statistical-classifier",
        }
        if not result["enabled"]:
            return result

        mem_kb, temp_millic, sensor_error = (
            self._sensors(config)
        )
        ready, ready_reason = self._python_ready(config)
        result.update({
            "mem_available_kb": mem_kb,
            "battery_temp_millic": temp_millic,
            "sensor_error": sensor_error or None,
            "python_ready": ready,
            "python_reason": ready_reason,
        })
        return result

