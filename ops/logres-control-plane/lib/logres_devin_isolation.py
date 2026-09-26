from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

from logres_devin import ISOLATION_ENV_VAR, PROTECTED_BRANCHES, redact


class IsolationError(RuntimeError):
    pass


ISOLATION_MARKER = "systemd/logres-devin-worker@.service"
UNIT_PREFIX = "logres-devin-"
NETNS_PREFIX = "logres-devin-"
NFT_TABLE_PREFIX = "logres_devin_"
NFT_FAMILY = "inet"
VETH_PREFIX = "ldv"
CONFIG_SCHEMA = "logres-devin-isolation-v1"
SYSTEMD_SYSTEM_MANAGER_DIR = "/run/systemd/system"
METADATA_IPV4 = "169.254.169.254/32"
METADATA_IPV6 = "fd00:ec2::254/128"
LOOPBACK_IPV4 = "127.0.0.0/8"
LOOPBACK_IPV6 = "::1/128"
LINKLOCAL_IPV6 = "fe80::/10"
EGRESS_DENY_LISTED = "deny-listed"
EGRESS_ALLOW_ONLY = "allow-only"
EGRESS_UNRESTRICTED = "unrestricted"
EGRESS_MODES = frozenset({EGRESS_DENY_LISTED, EGRESS_ALLOW_ONLY, EGRESS_UNRESTRICTED})

_UNIT_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")
_NFT_SAFE_RE = re.compile(r"[^A-Za-z0-9_]+")
_WORKER_BRANCH_RE = re.compile(r"^worker/[A-Za-z0-9._/-]+$")
_ENV_UNSAFE_RE = re.compile(r"[\s'\"]")

SANDBOX_KNOWN_ISSUE = (
    "Devin --sandbox wraps Exec subprocesses in bubblewrap+seccomp so the "
    "authenticated Devin control process stays outside the arbitrary Exec "
    "filesystem boundary. On this host bwrap initially failed with "
    "'bwrap: loopback: Failed RTM_NEWADDR' because "
    "kernel.apparmor_restrict_unprivileged_userns=1 denies unprivileged "
    "userns creation. A versioned narrow AppArmor profile granting userns "
    "to /usr/bin/bwrap restores the native sandbox while keeping the "
    "global restriction enabled; production_ready stays false until that "
    "profile plus bwrap and socat are proven."
)
BPF_FRAMEWORK_NOTE = (
    "systemd on this host is built -BPF_FRAMEWORK, so IPAddressAllow/Deny "
    "and SocketBind* properties are defense-in-depth only and are NOT the "
    "authoritative egress boundary. The authoritative boundary is a "
    "pre-created per-worker network namespace plus host nftables policy "
    "rendered by netns_setup_plan."
)
AUTH_EXPOSURE_NOTE = (
    "If the whole authenticated Devin process ran inside one filesystem "
    "namespace with its credential re-bound, Exec subprocesses in the same "
    "namespace could read the credential. The native bwrap Exec sandbox is "
    "therefore required for production: it is the only boundary that keeps "
    "Devin auth hidden from arbitrary Exec."
)

DEFAULT_CONFIG: dict = {
    "schema": CONFIG_SCHEMA,
    "enabled": True,
    "manager": "system",
    "isolation_marker": ISOLATION_MARKER,
    "unit_prefix": UNIT_PREFIX,
    "run_as_user": "ubuntu",
    "paths": {
        "work_root": "/home/ubuntu/logres/work",
        "base_checkout": "/home/ubuntu/logres/src/awakened-realms",
        "scratch_root": "/home/ubuntu/logres/scratch/devin-workers",
        "log_root": "/home/ubuntu/logres/logs/devin-workers",
        "state_root": "/home/ubuntu/logres/control/devin-isolation",
        "auth_bind_paths": [
            "/home/ubuntu/.config/devin",
            "/home/ubuntu/.local/share/devin",
        ],
        "readonly_bind_paths": [],
        "inaccessible_paths": [
            "/root",
            "/etc/ssh",
            "/etc/cloud",
            "/var/lib/cloud",
            "/run/secrets",
            "/home/ubuntu/.ssh",
            "/home/ubuntu/.aws",
            "/home/ubuntu/.azure",
            "/home/ubuntu/.config/gh",
            "/home/ubuntu/.docker",
            "/home/ubuntu/.gnupg",
            "/home/ubuntu/.kube",
            "/home/ubuntu/.oci",
            "/home/ubuntu/.gitconfig",
            "/home/ubuntu/logres/control",
            "/home/ubuntu/logres/private",
            "/home/ubuntu/logres/src/awakened-realms",
        ],
        "protected_prefixes": [
            "/home/ubuntu/logres/src/awakened-realms",
            "/home/ubuntu/logres/control",
            "/home/ubuntu/logres/private",
            "/home/ubuntu/.ssh",
            "/home/ubuntu/.aws",
            "/home/ubuntu/.azure",
            "/home/ubuntu/.config/gh",
            "/home/ubuntu/.docker",
            "/home/ubuntu/.gnupg",
            "/home/ubuntu/.kube",
            "/home/ubuntu/.oci",
            "/home/ubuntu/.gitconfig",
        ],
    },
    "systemd": {
        "protect_system": "strict",
        "protect_home": "tmpfs",
        "private_tmp": True,
        "private_devices": True,
        "no_new_privileges": True,
        "protect_kernel_tunables": True,
        "protect_kernel_modules": True,
        "protect_kernel_logs": True,
        "protect_control_groups": True,
        "protect_clock": True,
        "protect_hostname": True,
        "restrict_suid_sgid": True,
        "lock_personality": True,
        "restrict_realtime": True,
        "remove_ipc": True,
        "keyring_mode": "private",
        "device_policy": "closed",
        "restrict_namespaces": "~cgroup",
        "capability_bounding_set": "",
        "ambient_capabilities": "",
        "restrict_address_families": [
            "AF_UNIX",
            "AF_INET",
            "AF_INET6",
            "AF_NETLINK",
        ],
        "system_call_architectures": "native",
        "socket_bind_deny": "any",
        "umask": "0077",
        "kill_mode": "control-group",
        "kill_signal": "SIGTERM",
        "final_kill_signal": "SIGKILL",
        "send_sigkill": True,
        "timeout_stop_sec": 30,
    },
    "limits": {
        "memory_max": "4G",
        "memory_high": "3G",
        "cpu_quota": "300%",
        "tasks_max": 512,
        "runtime_max_sec": 7200,
    },
    "watchdog": {
        "wall_clock_seconds": 7200,
        "no_progress_seconds": 900,
        "poll_seconds": 15,
        "term_grace_seconds": 15,
        "kill_grace_seconds": 5,
    },
    "network": {
        "require_netns": True,
        "netns_root": "/run/netns",
        "netns_prefix": NETNS_PREFIX,
        "nft_table_family": NFT_FAMILY,
        "nft_table_prefix": NFT_TABLE_PREFIX,
        "veth_prefix": VETH_PREFIX,
        "address_pool": "10.210.0.0/16",
        "veth_index_modulo": 16384,
        "metadata_cidrs": [METADATA_IPV4, METADATA_IPV6],
        "deny_cidrs": [
            METADATA_IPV4,
            METADATA_IPV6,
            "169.254.0.0/16",
            LOOPBACK_IPV4,
            LOOPBACK_IPV6,
            LINKLOCAL_IPV6,
        ],
        "allowed_cidrs": [],
        "egress_mode": EGRESS_DENY_LISTED,
        "required_services": ["devin", "github", "npm", "pypi"],
        "emit_ip_address_policy": True,
        "host_forward_sysctls": ["net.ipv4.ip_forward"],
    },
    "sandbox": {
        "required_for_production": True,
        "required_binaries": ["bwrap", "socat"],
        "apparmor_profile": "/etc/apparmor.d/usr.bin.bwrap.logres",
        "apparmor_profiles_sysfs": "/sys/kernel/security/apparmor/profiles",
        "exec_probe": [
            "bwrap",
            "--unshare-all",
            "--ro-bind",
            "/",
            "/",
            "--dev",
            "/dev",
            "--proc",
            "/proc",
            "true",
        ],
        "credential_paths": [
            "/home/ubuntu/.config/devin",
            "/home/ubuntu/.local/share/devin",
        ],
        "known_issue": SANDBOX_KNOWN_ISSUE,
    },
    "environment": {
        "NPM_CONFIG_CACHE": "./npm-cache",
        "XDG_CACHE_HOME": "./home/.cache",
        "GIT_CONFIG_NOSYSTEM": "1",
    },
}


def default_config() -> dict:
    return json.loads(json.dumps(DEFAULT_CONFIG))


def deep_merge(base, override):
    if isinstance(base, dict) and isinstance(override, dict):
        out = dict(base)
        for key, value in override.items():
            out[key] = deep_merge(base.get(key), value)
        return out
    if override is None:
        return base
    return override


def _expect_list_of_str(value, label: str, problems: list[str]) -> None:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        problems.append(f"{label} must be a list of non-empty strings")


def validate_config(cfg: dict) -> None:
    problems: list[str] = []
    if not isinstance(cfg, dict):
        raise IsolationError("isolation config root must be a JSON object")
    if cfg.get("schema") != CONFIG_SCHEMA:
        problems.append(f"schema must be {CONFIG_SCHEMA!r}")
    if cfg.get("manager") != "system":
        problems.append(
            "manager must be 'system'; the systemd user manager is not an "
            "authoritative boundary on this host (ProtectHome is ignored)"
        )
    run_as = str(cfg.get("run_as_user") or "").strip()
    if not run_as or run_as == "root":
        problems.append("run_as_user must be a non-root account")
    for section in ("paths", "systemd", "limits", "watchdog", "network", "sandbox"):
        if not isinstance(cfg.get(section), dict):
            problems.append(f"{section} must be an object")
    if problems:
        raise IsolationError("invalid isolation config: " + "; ".join(problems))
    paths = cfg["paths"]
    for key in ("work_root", "base_checkout", "scratch_root", "log_root", "state_root"):
        value = str(paths.get(key) or "")
        if not value.startswith("/"):
            problems.append(f"paths.{key} must be an absolute path")
    for key in ("auth_bind_paths", "readonly_bind_paths", "inaccessible_paths", "protected_prefixes"):
        _expect_list_of_str(paths.get(key), f"paths.{key}", problems)
    net = cfg["network"]
    if str(net.get("egress_mode") or "") not in EGRESS_MODES:
        problems.append("network.egress_mode must be one of " + ", ".join(sorted(EGRESS_MODES)))
    if net.get("egress_mode") == EGRESS_UNRESTRICTED:
        problems.append("network.egress_mode 'unrestricted' is never production-safe")
    for key in ("metadata_cidrs", "deny_cidrs", "allowed_cidrs"):
        _expect_list_of_str(net.get(key), f"network.{key}", problems)
    for cidr in list(net.get("metadata_cidrs") or []) + list(net.get("deny_cidrs") or []) + list(net.get("allowed_cidrs") or []):
        try:
            ipaddress.ip_network(str(cidr), strict=False)
        except ValueError:
            problems.append(f"network cidr is invalid: {cidr}")
    try:
        ipaddress.ip_network(str(net.get("address_pool") or ""), strict=False)
    except ValueError:
        problems.append("network.address_pool is not a valid CIDR")
    sandbox = cfg["sandbox"]
    _expect_list_of_str(sandbox.get("required_binaries"), "sandbox.required_binaries", problems)
    _expect_list_of_str(sandbox.get("exec_probe"), "sandbox.exec_probe", problems)
    limits = cfg["limits"]
    for key in ("tasks_max", "runtime_max_sec"):
        if not isinstance(limits.get(key), (int, float)) or float(limits.get(key)) <= 0:
            problems.append(f"limits.{key} must be a positive number")
    watch = cfg["watchdog"]
    for key in ("wall_clock_seconds", "no_progress_seconds", "poll_seconds", "term_grace_seconds", "kill_grace_seconds"):
        if not isinstance(watch.get(key), (int, float)) or float(watch.get(key)) <= 0:
            problems.append(f"watchdog.{key} must be a positive number")
    if problems:
        raise IsolationError("invalid isolation config: " + "; ".join(problems))


def load_config(path=None) -> dict:
    cfg = default_config()
    if path is not None:
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise IsolationError(f"isolation config missing: {source}") from exc
        except json.JSONDecodeError as exc:
            raise IsolationError(f"isolation config is not valid JSON: {source}: {exc}") from exc
        if not isinstance(raw, dict):
            raise IsolationError("isolation config root must be a JSON object")
        cfg = deep_merge(cfg, raw)
    validate_config(cfg)
    return cfg


def safe_unit_component(value) -> str:
    cleaned = _UNIT_SAFE_RE.sub("-", str(value or "")).strip("-.")
    return cleaned[:48] or "worker"


def safe_nft_component(value) -> str:
    cleaned = _NFT_SAFE_RE.sub("_", str(value or "")).strip("_")
    return cleaned[:32] or "worker"


def _resolve(value) -> Path:
    return Path(os.path.realpath(str(value)))


def normalize_spec(cfg: dict, spec: dict) -> dict:
    if not isinstance(spec, dict):
        raise IsolationError("worker spec must be an object")
    out: dict = {}
    for key in ("task_id", "worker_id", "branch"):
        value = str(spec.get(key) or "").strip()
        if not value:
            raise IsolationError(f"worker spec missing {key}")
        out[key] = value
    branch = out["branch"]
    if branch in PROTECTED_BRANCHES:
        raise IsolationError("refusing protected branch: " + branch)
    if not _WORKER_BRANCH_RE.match(branch):
        raise IsolationError("worker branch must match worker/*: " + branch)
    worktree_raw = str(spec.get("worktree") or "").strip()
    if not worktree_raw:
        raise IsolationError("worker spec missing worktree")
    worktree = _resolve(worktree_raw)
    paths = cfg["paths"]
    base = _resolve(paths["base_checkout"])
    if worktree == base:
        raise IsolationError("refusing to isolate the protected primary checkout")
    work_root = _resolve(paths["work_root"])
    if worktree != work_root and work_root not in worktree.parents:
        raise IsolationError(
            f"worktree {worktree} is outside managed work root {work_root}"
        )
    out["worktree"] = worktree
    out["name"] = safe_unit_component(worktree.name or out["worker_id"])
    return out


def unit_name(cfg: dict, spec: dict) -> str:
    prefix = str(cfg.get("unit_prefix") or UNIT_PREFIX)
    return f"{prefix}{safe_unit_component(spec['name'])}.service"


def netns_name(cfg: dict, spec: dict) -> str:
    prefix = str(cfg["network"].get("netns_prefix") or NETNS_PREFIX)
    return f"{prefix}{safe_unit_component(spec['name'])[:24]}"


def nft_table_name(cfg: dict, spec: dict) -> str:
    prefix = str(cfg["network"].get("nft_table_prefix") or NFT_TABLE_PREFIX)
    return f"{prefix}{safe_nft_component(spec['name'])[:32]}"


def _veth_index(cfg: dict, spec: dict) -> int:
    modulo = int(cfg["network"].get("veth_index_modulo") or 16384)
    digest = hashlib.sha256(str(spec["name"]).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(1, modulo)


def veth_names(cfg: dict, spec: dict) -> tuple[str, str]:
    prefix = str(cfg["network"].get("veth_prefix") or VETH_PREFIX)
    idx = _veth_index(cfg, spec)
    return f"{prefix}{idx:04x}h", f"{prefix}{idx:04x}n"


def worker_subnet(cfg: dict, spec: dict) -> dict:
    pool = ipaddress.ip_network(str(cfg["network"]["address_pool"]), strict=False)
    idx = _veth_index(cfg, spec)
    host_octets = int(pool.network_address) + idx * 4
    if host_octets + 3 > int(pool.broadcast_address):
        raise IsolationError("network.address_pool exhausted for worker index")
    net = ipaddress.ip_network(f"{ipaddress.IPv4Address(host_octets)}/30")
    return {
        "network": str(net),
        "host_ip": str(net.network_address + 1),
        "guest_ip": str(net.network_address + 2),
        "index": idx,
    }


def resolve_paths(cfg: dict, spec: dict) -> dict:
    paths = cfg["paths"]
    name = spec["name"]
    scratch = _resolve(Path(paths["scratch_root"]) / name)
    logs = _resolve(Path(paths["log_root"]) / name)
    state_root = _resolve(paths["state_root"])
    return {
        "worktree": Path(spec["worktree"]),
        "scratch": scratch,
        "logs": logs,
        "home": scratch / "home",
        "npm_cache": scratch / "npm-cache",
        "state": state_root / f"{name}.json",
        "env_file": state_root / f"{name}.env",
        "log_file": logs / "devin.log",
        "progress_file": logs / "devin.log",
        "export_file": scratch / "session-export.json",
    }


def _is_within(path: Path, prefix: Path) -> bool:
    return path == prefix or prefix in path.parents


def build_binds(cfg: dict, spec: dict) -> dict:
    """Writable worktree/scratch/log binds, read-only extras, masked rest.

    ProtectHome=tmpfs hides all of /home; only the exact worker worktree,
    scratch, log, auth, and configured read-only paths are re-exposed via
    BindPaths/BindReadOnlyPaths (ReadWritePaths cannot re-expose a path under
    ProtectHome). Any bind overlapping a protected prefix — the primary
    checkout, control-plane state, private evidence, SSH/cloud/dotfile
    credentials — is refused so Exec inside the unit can never reach it.
    """
    paths = cfg["paths"]
    resolved = resolve_paths(cfg, spec)
    writable = [resolved["worktree"], resolved["scratch"], resolved["logs"]]
    auth = [_resolve(p) for p in paths["auth_bind_paths"]]
    readonly = [_resolve(p) for p in paths["readonly_bind_paths"]]
    protected = sorted(
        {_resolve(p) for p in paths["protected_prefixes"]}
        | {_resolve(paths["base_checkout"])}
    )
    seen = set()
    for label, group in (
        ("writable", writable),
        ("auth", auth),
        ("readonly", readonly),
    ):
        for bind in group:
            if bind in seen:
                continue
            seen.add(bind)
            for prefix in protected:
                if _is_within(bind, prefix) or _is_within(prefix, bind):
                    raise IsolationError(
                        f"{label} bind {bind} overlaps protected path {prefix}"
                    )
    inaccessible = sorted(
        {_resolve(p) for p in paths["inaccessible_paths"]}
        | {_resolve(paths["base_checkout"])}
    )
    return {
        "writable": sorted(set(writable)),
        "auth": auth,
        "readonly": readonly,
        "inaccessible": inaccessible,
        "protected": protected,
    }


def isolation_marker(cfg: dict, spec: dict) -> str:
    return f"systemd-run/system:{unit_name(cfg, spec)}"


def build_child_environment(cfg: dict, spec: dict) -> dict:
    resolved = resolve_paths(cfg, spec)
    scratch = resolved["scratch"]
    env = {
        "HOME": str(resolved["home"]),
        "TMPDIR": "/tmp",
        "GIT_CONFIG_GLOBAL": str(resolved["home"] / ".gitconfig"),
        "LOGRES_TASK_ID": spec["task_id"],
        "LOGRES_WORKER_ID": spec["worker_id"],
        "LOGRES_BRANCH": spec["branch"],
        "LOGRES_WORKTREE": str(resolved["worktree"]),
        "LOGRES_DEVIN_ISOLATION_UNIT": unit_name(cfg, spec),
        ISOLATION_ENV_VAR: isolation_marker(cfg, spec),
    }
    for key, value in (cfg.get("environment") or {}).items():
        text = str(value)
        if text.startswith("/"):
            env[str(key)] = text
        elif text.startswith("./"):
            env[str(key)] = str(scratch / text[2:])
        else:
            env[str(key)] = text
    for key, value in env.items():
        if _ENV_UNSAFE_RE.search(str(value)) or _ENV_UNSAFE_RE.search(str(key)):
            raise IsolationError(f"unsafe environment value for {key}")
    return env


def build_unit_properties(cfg: dict, spec: dict) -> list[str]:
    """Deterministic transient-unit properties for systemd-run --system."""
    resolved = resolve_paths(cfg, spec)
    binds = build_binds(cfg, spec)
    sysd = cfg["systemd"]
    limits = cfg["limits"]
    net = cfg["network"]
    props = [
        f"Description=Logres isolated Devin worker {spec['task_id']} ({spec['worker_id']})",
        f"User={cfg['run_as_user']}",
        f"WorkingDirectory={resolved['worktree']}",
        "NoNewPrivileges=yes" if sysd["no_new_privileges"] else "NoNewPrivileges=no",
        "PrivateTmp=yes" if sysd["private_tmp"] else "PrivateTmp=no",
        "PrivateDevices=yes" if sysd["private_devices"] else "PrivateDevices=no",
        f"ProtectSystem={sysd['protect_system']}",
        f"ProtectHome={sysd['protect_home']}",
        "ProtectKernelTunables=yes" if sysd["protect_kernel_tunables"] else "ProtectKernelTunables=no",
        "ProtectKernelModules=yes" if sysd["protect_kernel_modules"] else "ProtectKernelModules=no",
        "ProtectKernelLogs=yes" if sysd["protect_kernel_logs"] else "ProtectKernelLogs=no",
        "ProtectControlGroups=yes" if sysd["protect_control_groups"] else "ProtectControlGroups=no",
        "ProtectClock=yes" if sysd["protect_clock"] else "ProtectClock=no",
        "ProtectHostname=yes" if sysd["protect_hostname"] else "ProtectHostname=no",
        "RestrictSUIDSGID=yes" if sysd["restrict_suid_sgid"] else "RestrictSUIDSGID=no",
        "LockPersonality=yes" if sysd["lock_personality"] else "LockPersonality=no",
        "RestrictRealtime=yes" if sysd["restrict_realtime"] else "RestrictRealtime=no",
        "RemoveIPC=yes" if sysd["remove_ipc"] else "RemoveIPC=no",
        f"KeyringMode={sysd['keyring_mode']}",
        f"DevicePolicy={sysd['device_policy']}",
        f"RestrictNamespaces={sysd['restrict_namespaces']}",
        f"CapabilityBoundingSet={sysd['capability_bounding_set']}",
        f"AmbientCapabilities={sysd['ambient_capabilities']}",
        "RestrictAddressFamilies=" + " ".join(sysd["restrict_address_families"]),
        f"SystemCallArchitectures={sysd['system_call_architectures']}",
        f"SocketBindDeny={sysd['socket_bind_deny']}",
        f"UMask={sysd['umask']}",
        f"MemoryMax={limits['memory_max']}",
        f"MemoryHigh={limits['memory_high']}",
        f"CPUQuota={limits['cpu_quota']}",
        f"TasksMax={int(limits['tasks_max'])}",
        f"RuntimeMaxSec={int(limits['runtime_max_sec'])}",
        f"TimeoutStopSec={int(sysd['timeout_stop_sec'])}",
        f"KillMode={sysd['kill_mode']}",
        f"KillSignal={sysd['kill_signal']}",
        f"FinalKillSignal={sysd['final_kill_signal']}",
        "SendSIGKILL=yes" if sysd["send_sigkill"] else "SendSIGKILL=no",
        f"NetworkNamespacePath={net['netns_root']}/{netns_name(cfg, spec)}",
        f"StandardOutput=append:{resolved['log_file']}",
        f"StandardError=append:{resolved['log_file']}",
        f"SyslogIdentifier=logres-devin-{safe_unit_component(spec['name'])[:32]}",
    ]
    if net.get("emit_ip_address_policy"):
        deny = list(net.get("metadata_cidrs") or []) + list(net.get("deny_cidrs") or [])
        if deny:
            props.append("IPAddressDeny=" + " ".join(dict.fromkeys(deny)))
    for bind in binds["writable"] + binds["auth"]:
        props.append(f"BindPaths={bind}")
    for bind in binds["readonly"]:
        props.append(f"BindReadOnlyPaths={bind}")
    if binds["inaccessible"]:
        props.append(
            "InaccessiblePaths=" + " ".join(str(p) for p in binds["inaccessible"])
        )
    for key, value in build_child_environment(cfg, spec).items():
        props.append(f"Environment={key}={value}")
    return props


def build_systemd_run_argv(cfg: dict, spec: dict, child_argv) -> list[str]:
    child = [str(item) for item in child_argv or []]
    if not child:
        raise IsolationError("empty child argv for isolated unit")
    argv = [
        "systemd-run",
        "--system",
        f"--unit={unit_name(cfg, spec)}",
        "--service-type=exec",
        "--collect",
        "--quiet",
    ]
    for prop in build_unit_properties(cfg, spec):
        argv.append("--property")
        argv.append(prop)
    argv.append("--")
    argv.extend(child)
    return argv


def build_devin_child_argv(cfg: dict, child_argv) -> list[str]:
    argv = [str(item) for item in child_argv or []]
    if not argv:
        raise IsolationError("empty devin argv")
    if cfg["sandbox"].get("required_for_production") and "--sandbox" not in argv:
        argv.append("--sandbox")
    return argv


def netns_setup_plan(cfg: dict, spec: dict) -> list[list[str]]:
    """Privileged netns/veth/nftables setup for a root operator or helper.

    This renders the authoritative egress boundary; the tool never executes
    it. Deny-listed mode drops metadata, link-local, and host-loopback
    destinations while permitting the remaining egress the Devin/GitHub/
    package flows need. Allow-only mode additionally requires an explicit
    allowed_cidrs policy and fails closed when it is empty.
    """
    net = cfg["network"]
    ns = netns_name(cfg, spec)
    veth_h, veth_n = veth_names(cfg, spec)
    subnet = worker_subnet(cfg, spec)
    family = str(net["nft_table_family"])
    table = nft_table_name(cfg, spec)
    mode = str(net["egress_mode"])
    allowed = [str(c) for c in net.get("allowed_cidrs") or []]
    if mode == EGRESS_ALLOW_ONLY and not allowed:
        raise IsolationError(
            "network.egress_mode allow-only requires non-empty allowed_cidrs"
        )
    deny_v4: list[str] = []
    deny_v6: list[str] = []
    for cidr in dict.fromkeys(
        list(net.get("metadata_cidrs") or []) + list(net.get("deny_cidrs") or [])
    ):
        try:
            parsed = ipaddress.ip_network(str(cidr), strict=False)
        except ValueError:
            raise IsolationError(f"invalid deny cidr: {cidr}")
        (deny_v6 if parsed.version == 6 else deny_v4).append(str(parsed))
    plan: list[list[str]] = [
        ["ip", "netns", "add", ns],
        ["ip", "link", "add", veth_h, "type", "veth", "peer", "name", veth_n],
        ["ip", "link", "set", veth_n, "netns", ns],
        ["ip", "addr", "add", f"{subnet['host_ip']}/30", "dev", veth_h],
        ["ip", "link", "set", veth_h, "up"],
        ["ip", "-n", ns, "addr", "add", f"{subnet['guest_ip']}/30", "dev", veth_n],
        ["ip", "-n", ns, "link", "set", veth_n, "up"],
        ["ip", "-n", ns, "link", "set", "lo", "up"],
        ["ip", "-n", ns, "route", "add", "default", "via", subnet["host_ip"]],
        ["nft", "add", "table", family, table],
        [
            "nft", "add", "chain", family, table, "worker_in",
            "{", "type", "filter", "hook", "input", "priority", "-10", ";", "}",
        ],
        [
            "nft", "add", "chain", family, table, "worker_fwd",
            "{", "type", "filter", "hook", "forward", "priority", "-10", ";", "}",
        ],
        [
            "nft", "add", "chain", family, table, "worker_nat",
            "{", "type", "nat", "hook", "postrouting", "priority", "100", ";", "}",
        ],
    ]
    for chain in ("worker_in", "worker_fwd"):
        for cidr in deny_v4:
            plan.append(
                ["nft", "add", "rule", family, table, chain,
                 "iifname", veth_h, "ip", "daddr", cidr, "drop"]
            )
        for cidr in deny_v6:
            plan.append(
                ["nft", "add", "rule", family, table, chain,
                 "iifname", veth_h, "ip6", "daddr", cidr, "drop"]
            )
        if mode == EGRESS_ALLOW_ONLY:
            v4 = [str(ipaddress.ip_network(c, strict=False)) for c in allowed
                  if ipaddress.ip_network(c, strict=False).version == 4]
            v6 = [str(ipaddress.ip_network(c, strict=False)) for c in allowed
                  if ipaddress.ip_network(c, strict=False).version == 6]
            if v4:
                plan.append(
                    ["nft", "add", "rule", family, table, chain,
                     "iifname", veth_h, "ip", "daddr", "!=", "{ " + ", ".join(v4) + " }", "drop"]
                )
            if v6:
                plan.append(
                    ["nft", "add", "rule", family, table, chain,
                     "iifname", veth_h, "ip6", "daddr", "!=", "{ " + ", ".join(v6) + " }", "drop"]
                )
    plan.append(
        ["nft", "add", "rule", family, table, "worker_nat",
         "oifname", "!=", veth_h, "ip", "saddr", subnet["guest_ip"], "masquerade"]
    )
    for sysctl in net.get("host_forward_sysctls") or []:
        plan.append(["sysctl", "-w", f"{sysctl}=1"])
    return plan


def netns_teardown_plan(cfg: dict, spec: dict) -> list[list[str]]:
    net = cfg["network"]
    return [
        ["nft", "delete", "table", str(net["nft_table_family"]), nft_table_name(cfg, spec)],
        ["ip", "link", "delete", veth_names(cfg, spec)[0]],
        ["ip", "netns", "delete", netns_name(cfg, spec)],
    ]


def default_probes() -> dict:
    def run(argv, timeout=None):
        proc = subprocess.run(
            [str(a) for a in argv],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
        return SimpleNamespace(
            returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def git_branch(worktree):
        try:
            proc = run(
                ["git", "-C", str(worktree), "branch", "--show-current"],
                timeout=30,
            )
        except Exception:
            return None
        if proc.returncode:
            return None
        return (proc.stdout or "").strip() or None

    def read_text(path):
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    return {
        "exists": lambda p: Path(p).exists(),
        "is_dir": lambda p: Path(p).is_dir(),
        "which": lambda name: shutil.which(str(name)),
        "read_text": read_text,
        "run": run,
        "git_branch": git_branch,
        "euid": lambda: os.geteuid() if hasattr(os, "geteuid") else 0,
    }


def _check(checks: list, name: str, ok: bool, required: bool, detail: str) -> bool:
    checks.append(
        {"name": name, "ok": bool(ok), "required": bool(required), "detail": str(detail)}
    )
    return bool(ok)


def _deny_covers(deny_set: set, cidr: str) -> bool:
    try:
        target = ipaddress.ip_network(str(cidr), strict=False)
    except ValueError:
        return False
    for entry in deny_set:
        try:
            net = ipaddress.ip_network(str(entry), strict=False)
        except ValueError:
            continue
        if net.version == target.version and target.subnet_of(net):
            return True
    return False


def evaluate_preflight(cfg: dict, spec: dict, probes=None) -> dict:
    """Fail-closed readiness report for unattended isolated launch.

    production_ready requires every required check to pass: system manager,
    hardening render, exact writable binds, masked secrets/protected
    checkouts, per-worker netns plus nftables egress policy, and the native
    bwrap Exec sandbox (binaries, narrow AppArmor userns profile, exec
    probe). attended_ready relaxes only the native-sandbox group for
    supervised manual work; the network boundary is never relaxed.
    """
    probes = probes or default_probes()
    exists, is_dir = probes["exists"], probes["is_dir"]
    which, run = probes["which"], probes["run"]
    resolved = resolve_paths(cfg, spec)
    binds_error = None
    props: list[str] = []
    binds = {"writable": [], "auth": [], "readonly": [], "inaccessible": [], "protected": []}
    try:
        binds = build_binds(cfg, spec)
        props = build_unit_properties(cfg, spec)
    except IsolationError as exc:
        binds_error = str(exc)
    net = cfg["network"]
    sandbox = cfg["sandbox"]
    require_netns = bool(net.get("require_netns"))
    require_sandbox = bool(sandbox.get("required_for_production"))
    checks: list = []

    _check(
        checks, "system_manager",
        is_dir(SYSTEMD_SYSTEM_MANAGER_DIR),
        True,
        f"{SYSTEMD_SYSTEM_MANAGER_DIR} present (systemd --system manager; "
        "user manager is not authoritative: ProtectHome is ignored there)",
    )
    missing_bins = [
        name for name in ("systemd-run", "systemctl") if not which(name)
    ]
    _check(
        checks, "launcher_binaries", not missing_bins, True,
        "systemd-run/systemctl required" if missing_bins else "systemd tooling present",
    )
    worktree = resolved["worktree"]
    _check(
        checks, "worktree_layout",
        is_dir(worktree),
        True,
        f"worktree {worktree} under managed work root",
    )
    actual_branch = probes["git_branch"](worktree)
    _check(
        checks, "branch_contract",
        actual_branch is not None and actual_branch == spec["branch"],
        True,
        f"worktree branch proves lease contract ({actual_branch!r} == {spec['branch']!r})"
        if actual_branch is not None
        else "cannot prove worktree branch; refusing to launch unverified",
    )
    missing_dirs = [
        label for label in ("scratch", "logs", "home")
        if not is_dir(resolved[label])
    ]
    _check(
        checks, "writable_layout", not missing_dirs, True,
        "scratch/log/home dirs exist" if not missing_dirs
        else "missing prepared dirs: " + ", ".join(missing_dirs)
        + " (run logres-devin-isolate prepare)",
    )
    _check(
        checks, "bind_contract", binds_error is None, True,
        binds_error or "writable/auth/readonly binds clear protected paths",
    )
    required_props = [
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "ProtectSystem=strict",
        "ProtectHome=tmpfs",
        "RestrictSUIDSGID=yes",
        "LockPersonality=yes",
        "SendSIGKILL=yes",
        "DevicePolicy=closed",
        "CapabilityBoundingSet=",
        "AmbientCapabilities=",
        "RuntimeMaxSec=",
        "MemoryMax=",
        "CPUQuota=",
        "TasksMax=",
        "NetworkNamespacePath=",
        "BindPaths=",
        "InaccessiblePaths=",
    ]
    missing_props = [
        item for item in required_props
        if not any(prop == item or prop.startswith(item) for prop in props)
    ]
    _check(
        checks, "hardening_render", not missing_props, True,
        "hardening properties rendered" if not missing_props
        else "render missing: " + ", ".join(missing_props),
    )
    cap_ok = any(prop == "CapabilityBoundingSet=" for prop in props) and any(
        prop == "AmbientCapabilities=" for prop in props
    )
    _check(
        checks, "no_broad_privileges", cap_ok, True,
        "capability bounding set and ambient capabilities are empty",
    )
    ns_path = f"{net['netns_root']}/{netns_name(cfg, spec)}"
    _check(
        checks, "network_netns",
        exists(ns_path),
        require_netns,
        f"netns {ns_path} pre-created" if exists(ns_path)
        else f"netns {ns_path} missing (run the rendered netns plan as root)",
    )
    table = nft_table_name(cfg, spec)
    nft_ok = False
    nft_detail = "nftables policy not probed"
    try:
        proc = run(
            ["nft", "list", "table", str(net["nft_table_family"]), table],
            timeout=30,
        )
        nft_ok = int(proc.returncode) == 0
        nft_detail = (
            f"nftables table {table} present"
            if nft_ok
            else "nftables table missing: "
            + redact(((proc.stderr or "") + (proc.stdout or "")).strip()[:200])
        )
    except Exception as exc:
        nft_detail = f"nft probe failed: {type(exc).__name__}"
    _check(checks, "network_policy", nft_ok, require_netns, nft_detail)
    deny_set = {str(c) for c in net.get("deny_cidrs") or []}
    meta_ok = _deny_covers(deny_set, METADATA_IPV4)
    loop_ok = _deny_covers(deny_set, "127.0.0.1/32") and _deny_covers(
        deny_set, "::1/128"
    )
    _check(
        checks, "metadata_loopback_deny", meta_ok and loop_ok, True,
        "OCI metadata and host loopback denied in egress policy"
        if meta_ok and loop_ok
        else "egress policy does not provably deny metadata/loopback",
    )
    egress_ok = net["egress_mode"] != EGRESS_UNRESTRICTED and (
        net["egress_mode"] != EGRESS_ALLOW_ONLY or bool(net.get("allowed_cidrs"))
    )
    _check(
        checks, "egress_mode", egress_ok, True,
        f"egress_mode={net['egress_mode']}",
    )
    sandbox_bins_missing = [
        name for name in sandbox["required_binaries"] if not which(name)
    ]
    _check(
        checks, "sandbox_binaries", not sandbox_bins_missing, require_sandbox,
        "bwrap/socat present" if not sandbox_bins_missing
        else "missing native sandbox tools: " + ", ".join(sandbox_bins_missing),
    )
    profile = str(sandbox["apparmor_profile"])
    _check(
        checks, "sandbox_apparmor_profile", exists(profile), require_sandbox,
        f"narrow userns profile {profile} installed" if exists(profile)
        else f"narrow userns profile {profile} missing; bwrap fails "
        "RTM_NEWADDR under kernel.apparmor_restrict_unprivileged_userns=1",
    )
    sysfs = probes["read_text"](sandbox["apparmor_profiles_sysfs"])
    _check(
        checks,
        "sandbox_apparmor_enforced",
        bool(sysfs) and "bwrap" in sysfs,
        False,
        "bwrap userns profile enforced" if sysfs and "bwrap" in sysfs
        else "enforced profile not visible in apparmor sysfs (advisory)",
    )
    probe_argv = [str(a) for a in sandbox["exec_probe"]]
    probe_ok = False
    probe_detail = "native sandbox exec probe not run"
    if not sandbox_bins_missing:
        try:
            proc = run(probe_argv, timeout=30)
            probe_ok = int(proc.returncode) == 0
            probe_detail = (
                "bwrap userns exec probe passed"
                if probe_ok
                else "bwrap exec probe failed: "
                + redact(((proc.stderr or "") + (proc.stdout or "")).strip()[:200])
            )
        except Exception as exc:
            probe_detail = f"bwrap exec probe error: {type(exc).__name__}"
    _check(checks, "sandbox_exec_probe", probe_ok, require_sandbox, probe_detail)
    sandbox_ok = all(
        item["ok"]
        for item in checks
        if item["name"]
        in ("sandbox_binaries", "sandbox_apparmor_profile", "sandbox_exec_probe")
    )
    _check(
        checks, "auth_credential_guard",
        not binds["auth"] or sandbox_ok,
        True,
        AUTH_EXPOSURE_NOTE
        if binds["auth"] and not sandbox_ok
        else "Devin auth binds are gated by the native Exec sandbox",
    )
    blockers = [item["name"] for item in checks if item["required"] and not item["ok"]]
    attended_exempt = {
        "sandbox_binaries",
        "sandbox_apparmor_profile",
        "sandbox_exec_probe",
        "auth_credential_guard",
    }
    attended_blockers = [
        item["name"]
        for item in checks
        if item["required"] and not item["ok"] and item["name"] not in attended_exempt
    ]
    return {
        "unit": unit_name(cfg, spec),
        "netns": netns_name(cfg, spec),
        "nft_table": table,
        "network_namespace_path": ns_path,
        "isolation_marker": isolation_marker(cfg, spec),
        "checks": checks,
        "blockers": blockers,
        "production_ready": not blockers,
        "attended_ready": not attended_blockers,
        "notes": [BPF_FRAMEWORK_NOTE, SANDBOX_KNOWN_ISSUE, AUTH_EXPOSURE_NOTE],
    }


def prepare_layout(cfg: dict, spec: dict) -> list[str]:
    resolved = resolve_paths(cfg, spec)
    made: list[str] = []
    for key in ("scratch", "logs", "home", "npm_cache"):
        path = resolved[key]
        path.mkdir(parents=True, exist_ok=True)
        made.append(str(path))
    resolved["state"].parent.mkdir(parents=True, exist_ok=True)
    return made


def write_env_file(cfg: dict, spec: dict, extra: dict | None = None) -> Path:
    resolved = resolve_paths(cfg, spec)
    lines = {
        "LOGRES_TASK_ID": spec["task_id"],
        "LOGRES_WORKER_ID": spec["worker_id"],
        "LOGRES_BRANCH": spec["branch"],
        "LOGRES_WORKTREE": str(resolved["worktree"]),
        "LOGRES_DEVIN_ISOLATION_UNIT": unit_name(cfg, spec),
        ISOLATION_ENV_VAR: isolation_marker(cfg, spec),
        "HOME": str(resolved["home"]),
        "TMPDIR": "/tmp",
    }
    for key, value in (extra or {}).items():
        lines[str(key)] = str(value)
    text = "".join(f"{key}={value}\n" for key, value in sorted(lines.items()))
    path = resolved["env_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)
    return path


def watchdog_evaluate(
    *,
    now: float,
    started_epoch: float,
    last_progress_epoch: float,
    wall_clock_seconds: float,
    no_progress_seconds: float,
) -> dict:
    age = max(0.0, float(now) - float(started_epoch))
    idle = max(0.0, float(now) - float(last_progress_epoch))
    if age >= float(wall_clock_seconds):
        action, reason = "terminate", "wall_clock"
    elif idle >= float(no_progress_seconds):
        action, reason = "terminate", "no_progress"
    else:
        action, reason = "continue", None
    return {
        "action": action,
        "reason": reason,
        "age_seconds": round(age, 3),
        "idle_seconds": round(idle, 3),
        "wall_clock_seconds": float(wall_clock_seconds),
        "no_progress_seconds": float(no_progress_seconds),
        "remaining_wall_seconds": round(max(0.0, float(wall_clock_seconds) - age), 3),
        "remaining_idle_seconds": round(max(0.0, float(no_progress_seconds) - idle), 3),
    }


def termination_plan(unit: str, *, grace_seconds: float, kill_grace_seconds: float, prefix: str = UNIT_PREFIX) -> dict:
    if not str(unit).startswith(prefix) or not str(unit).endswith(".service"):
        raise IsolationError(f"refusing to terminate non-worker unit: {unit}")
    return {
        "unit": unit,
        "term": ["systemctl", "--system", "kill", "--kill-whom=all", "--signal=SIGTERM", unit],
        "poll": ["systemctl", "--system", "is-active", "--quiet", unit],
        "kill": ["systemctl", "--system", "kill", "--kill-whom=all", "--signal=SIGKILL", unit],
        "stop": ["systemctl", "--system", "stop", unit],
        "cleanup": ["systemctl", "--system", "reset-failed", unit],
        "grace_seconds": float(grace_seconds),
        "kill_grace_seconds": float(kill_grace_seconds),
    }


def terminate_unit(run, unit: str, *, grace_seconds: float, kill_grace_seconds: float, clock=time.monotonic, sleep=time.sleep) -> dict:
    """SIGTERM the whole unit cgroup, bounded grace, then SIGKILL + cleanup."""
    plan = termination_plan(
        unit, grace_seconds=grace_seconds, kill_grace_seconds=kill_grace_seconds
    )
    events: list[str] = []
    proc = run(plan["term"])
    events.append(f"sigterm rc={proc.returncode}")
    deadline = clock() + float(grace_seconds)
    active = True
    while clock() < deadline:
        probe = run(plan["poll"])
        if probe.returncode != 0:
            active = False
            break
        sleep(0.2)
    if active:
        probe = run(plan["poll"])
        active = probe.returncode == 0
    if active:
        proc = run(plan["kill"])
        events.append(f"sigkill rc={proc.returncode}")
        kill_deadline = clock() + float(kill_grace_seconds)
        while clock() < kill_deadline:
            probe = run(plan["poll"])
            if probe.returncode != 0:
                active = False
                break
            sleep(0.2)
    run(plan["stop"])
    run(plan["cleanup"])
    events.append("cleanup done")
    return {
        "unit": unit,
        "terminated": not active,
        "escalated": any(event.startswith("sigkill") for event in events),
        "events": events,
    }


def check_unit_name(cfg: dict, unit: str) -> str:
    value = str(unit or "").strip()
    prefix = str(cfg.get("unit_prefix") or UNIT_PREFIX)
    if not value.startswith(prefix) or not value.endswith(".service"):
        raise IsolationError(f"not a logres devin worker unit: {value}")
    return value
