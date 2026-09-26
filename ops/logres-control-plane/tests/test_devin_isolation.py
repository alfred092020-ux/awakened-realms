import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(TEST_DIR))
sys.path.insert(0, str(LIB_DIR))

from logres_devin_isolation import (
    BPF_FRAMEWORK_NOTE,
    ISOLATION_MARKER,
    SYSTEMD_SYSTEM_MANAGER_DIR,
    IsolationError,
    build_binds,
    build_child_environment,
    build_devin_child_argv,
    build_systemd_run_argv,
    build_unit_properties,
    check_unit_name,
    deep_merge,
    default_config,
    evaluate_preflight,
    isolation_marker,
    load_config,
    netns_name,
    netns_setup_plan,
    netns_teardown_plan,
    nft_table_name,
    normalize_spec,
    prepare_layout,
    resolve_paths,
    terminate_unit,
    termination_plan,
    unit_name,
    validate_config,
    veth_names,
    watchdog_evaluate,
    worker_subnet,
    write_env_file,
)


def make_cfg(tmp: str, **overrides) -> dict:
    cfg = default_config()
    root = Path(tmp)
    cfg["paths"]["work_root"] = str(root / "work")
    cfg["paths"]["base_checkout"] = str(root / "base")
    cfg["paths"]["scratch_root"] = str(root / "scratch")
    cfg["paths"]["log_root"] = str(root / "logs")
    cfg["paths"]["state_root"] = str(root / "state")
    cfg["paths"]["auth_bind_paths"] = [
        str(root / "home/.config/devin"),
        str(root / "home/.local/share/devin"),
    ]
    cfg["paths"]["readonly_bind_paths"] = [str(root / "tools")]
    cfg["paths"]["inaccessible_paths"] = [
        str(root / "secrets"),
        str(root / "home/.ssh"),
        str(root / "control"),
    ]
    cfg["paths"]["protected_prefixes"] = [
        str(root / "base"),
        str(root / "secrets"),
        str(root / "control"),
        str(root / "home/.ssh"),
    ]
    cfg["network"]["netns_root"] = str(root / "netns")
    cfg["sandbox"]["apparmor_profile"] = str(root / "apparmor/usr.bin.bwrap.logres")
    cfg["sandbox"]["apparmor_profiles_sysfs"] = str(root / "apparmor-sysfs/profiles")
    cfg = deep_merge(cfg, overrides) if overrides else cfg
    validate_config(cfg)
    return cfg


def make_spec(tmp: str, cfg: dict, **overrides) -> dict:
    wt = Path(cfg["paths"]["work_root"]) / "worker_w1-t1-1"
    wt.mkdir(parents=True, exist_ok=True)
    spec = {
        "task_id": "T-1",
        "worker_id": "w1",
        "branch": "worker/w1-t1",
        "worktree": str(wt),
    }
    spec.update(overrides)
    return normalize_spec(cfg, spec)


def make_probes(tmp: str, cfg: dict, spec: dict, **flags) -> dict:
    virtual_exists = set(flags.get("exists", ()))
    virtual_dirs = set(flags.get("dirs", ()))
    binaries = flags.get(
        "binaries",
        {"systemd-run": "/usr/bin/systemd-run", "systemctl": "/usr/bin/systemctl", "bwrap": "/usr/bin/bwrap", "socat": "/usr/bin/socat"},
    )
    nft_ok = flags.get("nft_ok", True)
    probe_ok = flags.get("probe_ok", True)
    branch = flags.get("branch", spec["branch"])
    sysfs = flags.get("sysfs", "usr.bin.bwrap.logres (enforce)\n")

    def exists(path):
        return str(path) in virtual_exists or Path(path).exists()

    def is_dir(path):
        return str(path) in virtual_dirs or Path(path).is_dir()

    def run(argv, timeout=None):
        argv = [str(a) for a in argv]
        if argv[:3] == ["nft", "list", "table"]:
            return SimpleNamespace(
                returncode=0 if nft_ok else 1,
                stdout="table inet x\n" if nft_ok else "",
                stderr="" if nft_ok else "Error: No such file or directory",
            )
        if argv and argv[0] == "bwrap":
            return SimpleNamespace(
                returncode=0 if probe_ok else 1,
                stdout="",
                stderr="" if probe_ok else "bwrap: loopback: Failed RTM_NEWADDR",
            )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    return {
        "exists": exists,
        "is_dir": is_dir,
        "which": lambda name: binaries.get(name),
        "read_text": lambda p: sysfs if str(p) == cfg["sandbox"]["apparmor_profiles_sysfs"] else None,
        "run": run,
        "git_branch": lambda wt: branch,
        "euid": lambda: 0,
    }


def ready_probes(tmp: str, cfg: dict, spec: dict, **flags) -> dict:
    prepare_layout(cfg, spec)
    apparmor = Path(cfg["sandbox"]["apparmor_profile"])
    apparmor.parent.mkdir(parents=True, exist_ok=True)
    apparmor.write_text("profile bwrap\n")
    ns_path = Path(cfg["network"]["netns_root"]) / netns_name(cfg, spec)
    ns_path.parent.mkdir(parents=True, exist_ok=True)
    ns_path.touch()
    exists = set(flags.pop("exists", ()))
    dirs = set(flags.pop("dirs", ()))
    exists.add(str(ns_path))
    exists.add(str(apparmor))
    dirs.add(SYSTEMD_SYSTEM_MANAGER_DIR)
    return make_probes(tmp, cfg, spec, exists=exists, dirs=dirs, **flags)


def check_by_name(report: dict, name: str) -> dict:
    for item in report["checks"]:
        if item["name"] == name:
            return item
    raise AssertionError(f"missing check {name}")


class ConfigTests(unittest.TestCase):
    def test_default_config_is_valid(self):
        validate_config(default_config())

    def test_repo_config_file_loads_and_validates(self):
        cfg = load_config(CONTROL_ROOT / "config" / "devin_isolation.json")
        self.assertEqual("logres-devin-isolation-v1", cfg["schema"])
        self.assertEqual("system", cfg["manager"])
        self.assertTrue(cfg["sandbox"]["required_for_production"])
        self.assertTrue(cfg["network"]["require_netns"])

    def test_malformed_config_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{ not json")
            with self.assertRaises(IsolationError) as ctx:
                load_config(bad)
            self.assertIn("not valid JSON", str(ctx.exception))
            bad.write_text('["list"]')
            with self.assertRaises(IsolationError):
                load_config(bad)
            bad.write_text('{"schema": "wrong"}')
            with self.assertRaises(IsolationError) as ctx:
                load_config(bad)
            self.assertIn("schema", str(ctx.exception))

    def test_missing_config_file_refused(self):
        with self.assertRaises(IsolationError) as ctx:
            load_config("/nonexistent/devin_isolation.json")
        self.assertIn("missing", str(ctx.exception))

    def test_user_manager_config_refused(self):
        with self.assertRaises(IsolationError) as ctx:
            validate_config(deep_merge(default_config(), {"manager": "user"}))
        self.assertIn("system", str(ctx.exception))

    def test_unrestricted_egress_refused(self):
        cfg = deep_merge(default_config(), {"network": {"egress_mode": "unrestricted"}})
        with self.assertRaises(IsolationError):
            validate_config(cfg)

    def test_bad_cidr_refused(self):
        cfg = deep_merge(default_config(), {"network": {"deny_cidrs": ["not-a-cidr"]}})
        with self.assertRaises(IsolationError):
            validate_config(cfg)


class SpecContractTests(unittest.TestCase):
    def test_protected_branches_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            for branch in ("main", "feat/logres-reconstruction"):
                with self.assertRaises(IsolationError) as ctx:
                    make_spec(tmp, cfg, branch=branch)
                self.assertIn("protected", str(ctx.exception))

    def test_non_worker_branch_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            with self.assertRaises(IsolationError):
                make_spec(tmp, cfg, branch="release/x")

    def test_primary_checkout_refused_as_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            base = Path(cfg["paths"]["base_checkout"])
            base.mkdir(parents=True)
            with self.assertRaises(IsolationError) as ctx:
                make_spec(tmp, cfg, worktree=str(base))
            self.assertIn("primary checkout", str(ctx.exception))

    def test_worktree_outside_work_root_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            outside = Path(tmp) / "elsewhere"
            outside.mkdir()
            with self.assertRaises(IsolationError) as ctx:
                make_spec(tmp, cfg, worktree=str(outside))
            self.assertIn("work root", str(ctx.exception))

    def test_symlink_escape_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            outside = Path(tmp) / "outside"
            outside.mkdir()
            link = Path(cfg["paths"]["work_root"]) / "worker_link"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(outside)
            with self.assertRaises(IsolationError):
                make_spec(tmp, cfg, worktree=str(link))

    def test_missing_spec_fields_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            for drop in ("task_id", "worker_id", "branch", "worktree"):
                spec = {
                    "task_id": "T", "worker_id": "w", "branch": "worker/w",
                    "worktree": str(Path(tmp) / "work" / "w"),
                }
                spec[drop] = ""
                with self.assertRaises(IsolationError):
                    normalize_spec(cfg, spec)


class PathIsolationTests(unittest.TestCase):
    def test_only_worktree_scratch_log_are_writable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            resolved = resolve_paths(cfg, spec)
            binds = build_binds(cfg, spec)
            self.assertEqual(
                {resolved["worktree"], resolved["scratch"], resolved["logs"]},
                set(binds["writable"]),
            )
            self.assertNotIn(Path(cfg["paths"]["work_root"]), binds["writable"])

    def test_auth_and_readonly_binds(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            binds = build_binds(cfg, spec)
            self.assertEqual(
                [str(p) for p in binds["auth"]],
                cfg["paths"]["auth_bind_paths"],
            )
            self.assertEqual([str(root) for root in binds["readonly"]], [str(Path(tmp) / "tools")])

    def test_protected_checkout_and_secrets_inaccessible(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            binds = build_binds(cfg, spec)
            flat = {str(p) for p in binds["inaccessible"]}
            for needle in ("base", "secrets", "control"):
                self.assertIn(str(Path(tmp) / needle), flat)
            self.assertIn(str(Path(tmp) / "home/.ssh"), flat)

    def test_bind_overlapping_protected_prefix_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            cfg["paths"]["readonly_bind_paths"] = [str(Path(tmp) / "secrets" / "sub")]
            with self.assertRaises(IsolationError) as ctx:
                build_binds(cfg, spec)
            self.assertIn("protected", str(ctx.exception))

    def test_bind_ancestor_of_protected_prefix_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            cfg["paths"]["readonly_bind_paths"] = [str(Path(tmp))]
            with self.assertRaises(IsolationError):
                build_binds(cfg, spec)

    def test_worktree_inside_protected_checkout_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            nested = Path(cfg["paths"]["work_root"]) / "w"
            nested.mkdir(parents=True)
            spec = make_spec(tmp, cfg, worktree=str(nested))
            cfg["paths"]["protected_prefixes"].append(str(nested.parent))
            with self.assertRaises(IsolationError):
                build_binds(cfg, spec)


class RenderTests(unittest.TestCase):
    def props(self, tmp):
        cfg = make_cfg(tmp)
        spec = make_spec(tmp, cfg)
        return cfg, spec, build_unit_properties(cfg, spec)

    def test_deterministic_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            argv1 = build_systemd_run_argv(cfg, spec, ["devin", "-p"])
            argv2 = build_systemd_run_argv(cfg, spec, ["devin", "-p"])
            self.assertEqual(argv1, argv2)
            self.assertEqual("systemd-run", argv1[0])
            self.assertIn("--system", argv1)
            self.assertIn("--", argv1)
            tail = argv1[argv1.index("--") + 1:]
            self.assertEqual(["devin", "-p"], tail)

    def test_hardening_properties_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, props = self.props(tmp)
            for needle in (
                "NoNewPrivileges=yes",
                "PrivateTmp=yes",
                "PrivateDevices=yes",
                "ProtectSystem=strict",
                "ProtectHome=tmpfs",
                "RestrictSUIDSGID=yes",
                "LockPersonality=yes",
                "RestrictRealtime=yes",
                "RemoveIPC=yes",
                "DevicePolicy=closed",
                "RestrictNamespaces=~cgroup",
                "CapabilityBoundingSet=",
                "AmbientCapabilities=",
                "SystemCallArchitectures=native",
                "SocketBindDeny=any",
                "SendSIGKILL=yes",
                "KillMode=control-group",
                "MemoryMax=4G",
                "CPUQuota=300%",
                "TasksMax=512",
                "RuntimeMaxSec=7200",
            ):
                self.assertIn(needle, props)

    def test_network_and_bind_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg, spec, props = self.props(tmp)
            ns_prop = f"NetworkNamespacePath={cfg['network']['netns_root']}/{netns_name(cfg, spec)}"
            self.assertIn(ns_prop, props)
            resolved = resolve_paths(cfg, spec)
            self.assertIn(f"BindPaths={resolved['worktree']}", props)
            self.assertIn(f"BindPaths={resolved['scratch']}", props)
            self.assertIn(f"BindPaths={resolved['logs']}", props)
            for auth in cfg["paths"]["auth_bind_paths"]:
                self.assertIn(f"BindPaths={auth}", props)
            self.assertIn(f"BindReadOnlyPaths={Path(tmp) / 'tools'}", props)
            deny = [p for p in props if p.startswith("IPAddressDeny=")]
            self.assertTrue(deny)
            self.assertIn("169.254.169.254", deny[0])
            self.assertIn("127.0.0.0/8", deny[0])
            inaccessible = [p for p in props if p.startswith("InaccessiblePaths=")]
            self.assertTrue(inaccessible)
            self.assertIn(str(Path(tmp) / "base"), inaccessible[0])
            self.assertIn(str(Path(tmp) / "home/.ssh"), inaccessible[0])

    def test_environment_marks_isolation_and_scratch_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            env = build_child_environment(cfg, spec)
            resolved = resolve_paths(cfg, spec)
            self.assertEqual(str(resolved["home"]), env["HOME"])
            self.assertEqual(spec["task_id"], env["LOGRES_TASK_ID"])
            self.assertEqual(unit_name(cfg, spec), env["LOGRES_DEVIN_ISOLATION_UNIT"])
            self.assertTrue(
                env["LOGRES_DEVIN_EXECUTION_ISOLATION"].startswith("systemd-run/system:")
            )
            self.assertTrue(env["NPM_CONFIG_CACHE"].startswith(str(resolved["scratch"])))
            props = build_unit_properties(cfg, spec)
            self.assertTrue(any(p.startswith("Environment=HOME=") for p in props))

    def test_empty_child_argv_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            with self.assertRaises(IsolationError):
                build_systemd_run_argv(cfg, spec, [])

    def test_sandbox_flag_appended_for_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            argv = build_devin_child_argv(cfg, ["devin", "-p"])
            self.assertIn("--sandbox", argv)
            argv2 = build_devin_child_argv(cfg, ["devin", "-p", "--sandbox"])
            self.assertEqual(1, argv2.count("--sandbox"))

    def test_unit_names_are_safe_and_derived(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            self.assertEqual("logres-devin-worker_w1-t1-1.service", unit_name(cfg, spec))
            self.assertTrue(netns_name(cfg, spec).startswith("logres-devin-"))
            self.assertTrue(nft_table_name(cfg, spec).startswith("logres_devin_"))
            self.assertRegex(nft_table_name(cfg, spec), r"^[A-Za-z0-9_]+$")
            host, guest = veth_names(cfg, spec)
            self.assertLessEqual(len(host), 15)
            self.assertLessEqual(len(guest), 15)
            subnet = worker_subnet(cfg, spec)
            self.assertIn("10.210.", subnet["host_ip"])
            self.assertIn("10.210.", subnet["guest_ip"])


class NetworkPolicyTests(unittest.TestCase):
    def test_netns_plan_creates_namespace_veth_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            plan = netns_setup_plan(cfg, spec)
            flat = [" ".join(argv) for argv in plan]
            self.assertIn(f"ip netns add {netns_name(cfg, spec)}", flat[0])
            self.assertTrue(any("type veth" in line for line in flat))
            self.assertTrue(any("masquerade" in line for line in flat))
            self.assertTrue(any("sysctl" in line and "ip_forward" in line for line in flat))

    def test_netns_plan_denies_metadata_loopback_linklocal(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            flat = " ".join(" ".join(a) for a in netns_setup_plan(cfg, spec))
            for needle in ("169.254.169.254", "169.254.0.0/16", "127.0.0.0/8", "::1/128", "fe80::/10"):
                self.assertIn(needle, flat)
            self.assertIn("drop", flat)
            for chain in ("worker_in", "worker_fwd"):
                self.assertIn(chain, flat)

    def test_allow_only_mode_fails_closed_without_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            cfg["network"]["egress_mode"] = "allow-only"
            cfg["network"]["allowed_cidrs"] = []
            with self.assertRaises(IsolationError):
                netns_setup_plan(cfg, spec)
            cfg["network"]["allowed_cidrs"] = ["140.82.0.0/16"]
            plan = netns_setup_plan(cfg, spec)
            flat = " ".join(" ".join(a) for a in plan)
            self.assertIn("140.82.0.0/16", flat)

    def test_teardown_plan_removes_policy_and_netns(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            flat = " ".join(" ".join(a) for a in netns_teardown_plan(cfg, spec))
            self.assertIn("nft delete table", flat)
            self.assertIn("ip netns delete", flat)


class PreflightTests(unittest.TestCase):
    def test_fully_ready_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            report = evaluate_preflight(cfg, spec, probes=ready_probes(tmp, cfg, spec))
            self.assertTrue(report["production_ready"], report["blockers"])
            self.assertTrue(report["attended_ready"])
            self.assertEqual([], report["blockers"])
            self.assertEqual(unit_name(cfg, spec), report["unit"])
            self.assertIn(BPF_FRAMEWORK_NOTE, report["notes"])

    def test_missing_system_manager_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec)
            real_is_dir = probes["is_dir"]
            probes["is_dir"] = (
                lambda p: False
                if str(p) == SYSTEMD_SYSTEM_MANAGER_DIR
                else real_is_dir(p)
            )
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertFalse(report["production_ready"])
            self.assertIn("system_manager", report["blockers"])

    def test_missing_systemd_binaries_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec, binaries={"bwrap": "/usr/bin/bwrap", "socat": "/usr/bin/socat"})
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertFalse(report["production_ready"])
            self.assertIn("launcher_binaries", report["blockers"])

    def test_missing_netns_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec)
            ns_path = Path(cfg["network"]["netns_root"]) / netns_name(cfg, spec)
            ns_path.unlink()
            probes["exists"] = lambda p: Path(p).exists()
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertFalse(report["production_ready"])
            self.assertIn("network_netns", report["blockers"])
            self.assertFalse(check_by_name(report, "network_netns")["ok"])

    def test_missing_nft_policy_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec, nft_ok=False)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("network_policy", report["blockers"])

    def test_missing_bwrap_or_socat_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            binaries = {"systemd-run": "x", "systemctl": "x", "socat": "x"}
            probes = ready_probes(tmp, cfg, spec, binaries=binaries)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("sandbox_binaries", report["blockers"])
            self.assertIn("sandbox_exec_probe", report["blockers"])
            self.assertIn("auth_credential_guard", report["blockers"])

    def test_missing_apparmor_profile_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec)
            Path(cfg["sandbox"]["apparmor_profile"]).unlink()
            probes["exists"] = lambda p: Path(p).exists()
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("sandbox_apparmor_profile", report["blockers"])
            detail = check_by_name(report, "sandbox_apparmor_profile")["detail"]
            self.assertIn("RTM_NEWADDR", detail)

    def test_bwrap_probe_failure_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec, probe_ok=False)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("sandbox_exec_probe", report["blockers"])
            detail = check_by_name(report, "sandbox_exec_probe")["detail"]
            self.assertIn("RTM_NEWADDR", detail)

    def test_branch_mismatch_refuses_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec, branch="worker/other")
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("branch_contract", report["blockers"])
            probes = ready_probes(tmp, cfg, spec, branch=None)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("branch_contract", report["blockers"])

    def test_missing_scratch_layout_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec)
            shutil.rmtree(Path(cfg["paths"]["scratch_root"]) / spec["name"])
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("writable_layout", report["blockers"])

    def test_missing_worktree_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            probes = ready_probes(tmp, cfg, spec)
            shutil.rmtree(spec["worktree"])
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("worktree_layout", report["blockers"])

    def test_attended_ready_ignores_sandbox_group_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            binaries = {"systemd-run": "x", "systemctl": "x"}
            probes = ready_probes(tmp, cfg, spec, binaries=binaries)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertFalse(report["production_ready"])
            self.assertTrue(report["attended_ready"])
            probes = ready_probes(tmp, cfg, spec, nft_ok=False)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertFalse(report["attended_ready"])

    def test_bind_contract_failure_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            cfg["paths"]["readonly_bind_paths"] = [str(Path(tmp))]
            probes = ready_probes(tmp, cfg, spec)
            report = evaluate_preflight(cfg, spec, probes=probes)
            self.assertIn("bind_contract", report["blockers"])
            self.assertIn("hardening_render", report["blockers"])


class WatchdogTests(unittest.TestCase):
    def test_continue_under_limits(self):
        decision = watchdog_evaluate(
            now=1000.0, started_epoch=100.0, last_progress_epoch=990.0,
            wall_clock_seconds=7200, no_progress_seconds=900,
        )
        self.assertEqual("continue", decision["action"])
        self.assertIsNone(decision["reason"])

    def test_wall_clock_terminates(self):
        decision = watchdog_evaluate(
            now=10000.0, started_epoch=100.0, last_progress_epoch=9990.0,
            wall_clock_seconds=7200, no_progress_seconds=900,
        )
        self.assertEqual("terminate", decision["action"])
        self.assertEqual("wall_clock", decision["reason"])

    def test_no_progress_terminates(self):
        decision = watchdog_evaluate(
            now=1000.0, started_epoch=100.0, last_progress_epoch=50.0,
            wall_clock_seconds=7200, no_progress_seconds=900,
        )
        self.assertEqual("terminate", decision["action"])
        self.assertEqual("no_progress", decision["reason"])
        self.assertEqual(950.0, decision["idle_seconds"])


class TerminationTests(unittest.TestCase):
    def test_plan_is_term_then_kill_then_cleanup(self):
        plan = termination_plan(
            "logres-devin-x.service", grace_seconds=15, kill_grace_seconds=5
        )
        self.assertIn("--signal=SIGTERM", plan["term"])
        self.assertIn("--kill-whom=all", plan["term"])
        self.assertIn("--signal=SIGKILL", plan["kill"])
        self.assertIn("reset-failed", plan["cleanup"])
        self.assertIn("--system", plan["term"])

    def test_foreign_unit_refused(self):
        with self.assertRaises(IsolationError):
            termination_plan("ssh.service", grace_seconds=1, kill_grace_seconds=1)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            with self.assertRaises(IsolationError):
                check_unit_name(cfg, "cron.service")
            self.assertEqual(
                "logres-devin-x.service",
                check_unit_name(cfg, "logres-devin-x.service"),
            )

    def test_terminate_escalates_after_grace(self):
        calls = []

        def run(argv, timeout=None):
            calls.append(argv)
            if "is-active" in argv:
                return SimpleNamespace(returncode=0, stdout="active\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        clock_now = [0.0]

        def clock():
            value = clock_now[0]
            clock_now[0] += 10.0
            return value

        result = terminate_unit(
            run, "logres-devin-x.service",
            grace_seconds=15, kill_grace_seconds=5,
            clock=clock, sleep=lambda s: None,
        )
        sigs = [a for argv in calls for a in argv if a.startswith("--signal=")]
        self.assertEqual(["--signal=SIGTERM", "--signal=SIGKILL"], sigs)
        self.assertTrue(result["escalated"])
        self.assertIn("reset-failed", calls[-1])

    def test_terminate_stops_after_clean_exit(self):
        calls = []

        def run(argv, timeout=None):
            calls.append(argv)
            if "is-active" in argv:
                return SimpleNamespace(returncode=3, stdout="inactive\n", stderr="")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        result = terminate_unit(
            run, "logres-devin-x.service",
            grace_seconds=15, kill_grace_seconds=5,
            sleep=lambda s: None,
        )
        self.assertTrue(result["terminated"])
        self.assertFalse(result["escalated"])
        sigs = [a for argv in calls for a in argv if a.startswith("--signal=")]
        self.assertEqual(["--signal=SIGTERM"], sigs)


class LayoutAndStateTests(unittest.TestCase):
    def test_prepare_creates_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            made = prepare_layout(cfg, spec)
            resolved = resolve_paths(cfg, spec)
            for key in ("scratch", "logs", "home", "npm_cache"):
                self.assertTrue(resolved[key].is_dir(), key)
                self.assertIn(str(resolved[key]), made)
            self.assertTrue(resolved["state"].parent.is_dir())

    def test_env_file_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            path = write_env_file(cfg, spec, extra={"DEVIN_ARGV_JSON": '["devin","-p"]'})
            text = path.read_text()
            self.assertIn("LOGRES_TASK_ID=T-1", text)
            self.assertIn("LOGRES_BRANCH=worker/w1-t1", text)
            self.assertIn("LOGRES_DEVIN_EXECUTION_ISOLATION=systemd-run/system:", text)
            self.assertIn("DEVIN_ARGV_JSON=", text)

    def test_marker_matches_agent_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = make_cfg(tmp)
            spec = make_spec(tmp, cfg)
            marker = isolation_marker(cfg, spec)
            self.assertRegex(marker, r"^[A-Za-z0-9._:+@/-]{1,128}$")
            self.assertTrue(marker.startswith("systemd-run/system:logres-devin-"))
            self.assertEqual("systemd/logres-devin-worker@.service", ISOLATION_MARKER)


class DeployedFileContractTests(unittest.TestCase):
    def test_bin_exposes_isolation_subcommands(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-isolate").read_text()
        for sub in ("preflight", "render", "prepare", "netns-plan", "start", "stop", "status", "watchdog", "exec-child"):
            self.assertIn(f'"{sub}"', script)
        for needle in (
            "evaluate_preflight",
            "build_systemd_run_argv",
            "terminate_unit",
            "watchdog_evaluate",
            "production_ready",
            "fail closed",
        ):
            self.assertIn(needle, script)

    def test_bin_has_no_credential_reads_or_secret_argv(self):
        script = (CONTROL_ROOT / "bin" / "logres-devin-isolate").read_text()
        for needle in ("api_key", "api-key", "client_secret", ".ssh/id"):
            self.assertNotIn(needle, script)

    def test_service_template_mirrors_hardening_contract(self):
        unit = (CONTROL_ROOT / "systemd" / "logres-devin-worker@.service").read_text()
        for needle in (
            "ProtectSystem=strict",
            "ProtectHome=tmpfs",
            "NoNewPrivileges=yes",
            "PrivateTmp=yes",
            "CapabilityBoundingSet=",
            "NetworkNamespacePath=/run/netns/logres-devin-%i",
            "IPAddressDeny=169.254.169.254/32",
            "RuntimeMaxSec=",
            "KillMode=control-group",
            "BindPaths=/home/ubuntu/logres/work/%i",
            "InaccessiblePaths=",
            "EnvironmentFile=-/home/ubuntu/logres/control/devin-isolation/%i.env",
            "LOGRES_DEVIN_EXECUTION_ISOLATION=systemd/logres-devin-worker@.service",
        ):
            self.assertIn(needle, unit)
        self.assertIn("RTM_NEWADDR", unit)
        self.assertIn("-BPF_FRAMEWORK", unit)
        self.assertIn("/home/ubuntu/.ssh", unit)
        self.assertIn("logres-devin-isolate exec-child", unit)


if __name__ == "__main__":
    unittest.main()
