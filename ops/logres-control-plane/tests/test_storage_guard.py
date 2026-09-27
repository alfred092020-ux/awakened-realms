import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = CONTROL_ROOT.parents[1]
sys.path.insert(0, str(CONTROL_ROOT / "lib"))

from logres_storage_guard import (
    StorageGuardError,
    apply_guard,
    classify_pressure,
    fanout_guard,
    collect_protected_paths,
    inventory_storage,
    load_policy,
    plan_cleanup,
    run_existing_gc,
    sync_brownout,
    validate_policy,
)


class StorageGuardTests(unittest.TestCase):
    def policy(self):
        return {
            "schema": "logres-storage-retention/1",
            "thresholds": {
                "warning_free_gib": 60.0,
                "high_free_gib": 40.0,
                "critical_free_gib": 30.0,
            },
            "expected_autonomy_min_free_disk_gib": 30.0,
            "protected_roots": ["control", "index", "artifacts"],
            "inventory_roots": [
                {"name": "logs", "path": "logs", "kind": "logs"},
                {"name": "cache", "path": "cache", "kind": "cache"},
                {"name": "artifacts", "path": "artifacts", "kind": "evidence"},
                {"name": "tmp", "path": "tmp", "kind": "scratch"},
            ],
            "retention_tiers": [
                {
                    "name": "capacity_scratch",
                    "root": "scratch",
                    "patterns": ["capacity-*"],
                    "min_age_hours": {"warning": 72, "high": 24, "critical": 6},
                },
                {
                    "name": "logs",
                    "root": "logs",
                    "patterns": ["verify-farm-*.log", "finish-*.log", "preflight-*.log"],
                    "min_age_hours": {"warning": 336, "high": 168, "critical": 72},
                },
            ],
            "workspace_gc": {
                "enabled": True,
                "workspace_limit": 25,
                "worktree_age_hours": 24,
                "preview_age_hours": 2,
            },
            "brownout": {
                "autoflow_config": "control/autoflow.json",
                "state_path": "control/storage-pressure.json",
            },
            "audit_root": "artifacts/storage-guard",
        }

    def test_pressure_bands_fail_closed_for_new_fanout_at_critical(self):
        gib = 1024 ** 3
        policy = self.policy()
        self.assertEqual("normal", classify_pressure(80 * gib, policy)["band"])
        self.assertEqual("warning", classify_pressure(55 * gib, policy)["band"])
        self.assertEqual("high", classify_pressure(35 * gib, policy)["band"])
        critical = classify_pressure(25 * gib, policy)
        self.assertEqual("critical", critical["band"])
        self.assertFalse(critical["allow_new_fanout"])
        self.assertTrue(critical["preserve_brain_writes"])
        self.assertTrue(critical["preserve_verifier_writes"])

    def test_policy_rejects_retention_inside_protected_roots(self):
        policy = self.policy()
        policy["retention_tiers"].append(
            {
                "name": "bad",
                "root": "artifacts",
                "patterns": ["*"],
                "min_age_hours": {"warning": 1, "high": 1, "critical": 1},
            }
        )
        with self.assertRaisesRegex(ValueError, "protected"):
            validate_policy(policy)

    def test_inventory_reports_largest_roots_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, size in (("logs", 12), ("cache", 40), ("artifacts", 25), ("tmp", 3)):
                path = root / name
                path.mkdir()
                (path / "payload.bin").write_bytes(b"x" * size)
            report = inventory_storage(root, self.policy())
            self.assertEqual(["cache", "artifacts", "logs", "tmp"], [r["name"] for r in report["roots"]])
            self.assertTrue(all((root / r["name"] / "payload.bin").exists() for r in report["roots"]))
            self.assertTrue(next(r for r in report["roots"] if r["name"] == "artifacts")["protected"])

    def test_database_referenced_evidence_and_logs_are_protected(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            create table brain_events(artifact_path text);
            create table integration_preflights(verification_log text);
            create table regressions(logs_json text);
            create table device_proofs(artifact_path text);
            """
        )
        conn.execute("insert into brain_events values('/safe/evidence.json')")
        conn.execute("insert into integration_preflights values('/safe/preflight.log')")
        conn.execute("insert into regressions values(?)", (json.dumps(["/safe/regression.log", {"nested": "/safe/nested.log"}]),))
        conn.execute("insert into device_proofs values('/safe/device.json')")
        protected = collect_protected_paths(conn)
        for path in (
            "/safe/evidence.json",
            "/safe/preflight.log",
            "/safe/regression.log",
            "/safe/nested.log",
            "/safe/device.json",
        ):
            self.assertIn(str(Path(path)), protected)
        conn.close()

    def test_protected_paths_are_schema_driven_across_brain_artifact_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript(
            """
            create table ai_runs(artifact_path text, artifact_sha text);
            create table correctness_receipts(receipt_json text, receipt_sha256 text);
            create table visual_truth_checks(reference_artifact text, observed_artifact text);
            create table branch_files(path text);
            """
        )
        conn.execute("insert into ai_runs values('/safe/ai-result.json','abc')")
        conn.execute(
            "insert into correctness_receipts values(?,?)",
            (json.dumps({"evidence": {"source_db": "/dev/shm/logres/verify-farm-proof.sqlite"}}), "def"),
        )
        conn.execute("insert into visual_truth_checks values('/safe/reference.png','/safe/observed.png')")
        conn.execute("insert into branch_files values('relative/repository/path.ts')")
        protected = collect_protected_paths(conn)
        for path in (
            "/safe/ai-result.json",
            "/dev/shm/logres/verify-farm-proof.sqlite",
            "/safe/reference.png",
            "/safe/observed.png",
        ):
            self.assertIn(str(Path(path)), protected)
        self.assertNotIn(str(Path("relative/repository/path.ts").resolve()), protected)
        conn.close()

    def test_cleanup_plan_selects_only_old_unreferenced_disposable_entries(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tmp").mkdir()
            (root / "scratch").mkdir()
            (root / "logs").mkdir()
            (root / "artifacts").mkdir()
            now = 2_000_000.0
            old = root / "scratch" / "capacity-old"
            referenced = root / "scratch" / "capacity-referenced"
            fresh = root / "scratch" / "capacity-fresh"
            log = root / "logs" / "verify-farm-old.log"
            evidence = root / "artifacts" / "historical.json"
            ambiguous_tmp = root / "tmp" / "public-current-jp"
            for path in (old, referenced, fresh, log, evidence, ambiguous_tmp):
                path.write_bytes(b"x" * 10)
            os.utime(old, (now - 30 * 3600, now - 30 * 3600))
            os.utime(referenced, (now - 30 * 3600, now - 30 * 3600))
            os.utime(fresh, (now - 2 * 3600, now - 2 * 3600))
            os.utime(log, (now - 200 * 3600, now - 200 * 3600))
            os.utime(evidence, (now - 500 * 3600, now - 500 * 3600))
            os.utime(ambiguous_tmp, (now - 500 * 3600, now - 500 * 3600))
            plan = plan_cleanup(
                root,
                self.policy(),
                "high",
                now_epoch=now,
                protected_paths={str(referenced.resolve())},
            )
            selected = {Path(item["path"]).name for item in plan["candidates"]}
            self.assertEqual({"capacity-old", "verify-farm-old.log"}, selected)
            self.assertTrue(any(item["reason"] == "REFERENCED_EVIDENCE" for item in plan["skipped"]))
            self.assertTrue(evidence.exists())
            self.assertTrue(ambiguous_tmp.exists())
            self.assertNotIn("public-current-jp", selected)

    def test_apply_guard_writes_auditable_manifest_and_reclaimed_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("tmp", "scratch", "logs", "cache", "artifacts", "control", "index", "bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            victim = root / "scratch" / "capacity-victim"
            victim.write_bytes(b"x" * 64)
            now = time.time()
            os.utime(victim, (now - 30 * 3600, now - 30 * 3600))
            (root / "control" / "autoflow.json").write_text(json.dumps({"swarm": {"enabled": True}}))
            conn = sqlite3.connect(":memory:")
            conn.executescript(
                """
                create table brain_events(artifact_path text);
                create table integration_preflights(verification_log text);
                create table regressions(logs_json text);
                create table device_proofs(artifact_path text);
                """
            )
            free_values = iter((35 * 1024**3, 36 * 1024**3, 36 * 1024**3))
            calls = []

            def fake_free(_path):
                return next(free_values)

            def fake_runner(argv, **kwargs):
                calls.append([str(x) for x in argv])
                return subprocess.CompletedProcess(argv, 0, stdout='{"ok":true}', stderr="")

            result = apply_guard(
                root,
                conn,
                self.policy(),
                now_epoch=now,
                runner=fake_runner,
                free_bytes_fn=fake_free,
            )
            conn.close()
            self.assertFalse(victim.exists())
            self.assertGreaterEqual(result["direct_cleanup"]["removed_bytes"], 64)
            self.assertGreater(result["filesystem_reclaimed_bytes"], 0)
            manifest = Path(result["manifest_path"])
            self.assertTrue(manifest.is_file())
            saved = json.loads(manifest.read_text())
            self.assertEqual("COMPLETE", saved["status"])
            self.assertTrue(saved["direct_cleanup"]["actions"])
            self.assertTrue(any("logres-workspace-gc" in " ".join(c) for c in calls))
            self.assertTrue(any("logres-worktree-gc" in " ".join(c) for c in calls))
            self.assertTrue(any("logres-preview-reaper" in " ".join(c) for c in calls))

    def test_fanout_guard_blocks_only_critical_and_recovers_after_pressure_clears(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "control").mkdir()
            config = root / "control" / "autoflow.json"
            state = root / "control" / "storage-pressure.json"
            config.write_text(json.dumps({"swarm": {"enabled": True}}))
            critical = fanout_guard(
                root, self.policy(), config, state,
                free_bytes_fn=lambda _path: 25 * 1024**3,
            )
            self.assertFalse(critical["allow_new_fanout"])
            self.assertEqual("critical", critical["band"])
            self.assertTrue(critical["brownout"]["active"])
            self.assertFalse(json.loads(config.read_text())["swarm"]["enabled"])
            recovered = fanout_guard(
                root, self.policy(), config, state,
                free_bytes_fn=lambda _path: 35 * 1024**3,
            )
            self.assertTrue(recovered["allow_new_fanout"])
            self.assertEqual("high", recovered["band"])
            self.assertTrue(recovered["brownout"]["restored"])
            self.assertTrue(json.loads(config.read_text())["swarm"]["enabled"])

    def test_manifest_prepare_failure_aborts_before_any_destructive_action(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("scratch", "logs", "cache", "artifacts", "control", "index", "bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            victim = root / "scratch" / "capacity-old"
            victim.write_bytes(b"x" * 64)
            old = time.time() - 30 * 3600
            os.utime(victim, (old, old))
            (root / "control" / "autoflow.json").write_text(json.dumps({"swarm": {"enabled": True}}))
            conn = sqlite3.connect(":memory:")
            conn.executescript(
                """
                create table brain_events(artifact_path text);
                create table integration_preflights(verification_log text);
                create table regressions(logs_json text);
                create table device_proofs(artifact_path text);
                """
            )
            calls = []

            def runner(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

            def broken_writer(_path, _payload):
                raise OSError("audit storage unavailable")

            with self.assertRaisesRegex(OSError, "audit storage unavailable"):
                apply_guard(
                    root,
                    conn,
                    self.policy(),
                    runner=runner,
                    free_bytes_fn=lambda _path: 35 * 1024**3,
                    manifest_writer=broken_writer,
                )
            conn.close()
            self.assertTrue(victim.exists())
            self.assertEqual([], calls)
            self.assertTrue(json.loads((root / "control" / "autoflow.json").read_text())["swarm"]["enabled"])

    def test_delegated_gc_failure_stops_direct_cleanup_with_failure_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("scratch", "logs", "cache", "artifacts", "control", "index", "bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            victim = root / "scratch" / "capacity-old"
            victim.write_bytes(b"x" * 64)
            old = time.time() - 30 * 3600
            os.utime(victim, (old, old))
            (root / "control" / "autoflow.json").write_text(json.dumps({"swarm": {"enabled": True}}))
            conn = sqlite3.connect(":memory:")
            conn.executescript(
                """
                create table brain_events(artifact_path text);
                create table integration_preflights(verification_log text);
                create table regressions(logs_json text);
                create table device_proofs(artifact_path text);
                """
            )
            calls = []

            def failing_runner(argv, **kwargs):
                manifests = list((root / "artifacts" / "storage-guard").glob("*.json"))
                self.assertEqual(1, len(manifests), "audit manifest must exist before delegated GC")
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 7, stdout="partial", stderr="delegated failure")

            with self.assertRaises(StorageGuardError) as caught:
                apply_guard(
                    root,
                    conn,
                    self.policy(),
                    runner=failing_runner,
                    free_bytes_fn=lambda _path: 35 * 1024**3,
                )
            conn.close()
            self.assertTrue(victim.exists())
            self.assertEqual(1, len(calls))
            manifest = Path(caught.exception.manifest_path)
            self.assertTrue(manifest.is_file())
            saved = json.loads(manifest.read_text())
            self.assertEqual("FAILED_DELEGATED_GC", saved["status"])
            self.assertEqual(7, saved["delegated_cleanup"][0]["returncode"])
            self.assertIsNone(saved.get("direct_cleanup"))

    def test_brownout_failure_is_audited_and_aborts_before_cleanup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("scratch", "logs", "cache", "artifacts", "control", "index", "bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            victim = root / "scratch" / "capacity-old"
            victim.write_bytes(b"x" * 64)
            old = time.time() - 30 * 3600
            os.utime(victim, (old, old))
            (root / "control" / "autoflow.json").write_text("{broken-json")
            conn = sqlite3.connect(":memory:")
            calls = []

            def runner(argv, **kwargs):
                calls.append(argv)
                return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

            with self.assertRaises(StorageGuardError) as caught:
                apply_guard(
                    root,
                    conn,
                    self.policy(),
                    runner=runner,
                    free_bytes_fn=lambda _path: 25 * 1024**3,
                )
            conn.close()
            self.assertTrue(victim.exists())
            self.assertEqual([], calls)
            manifest = Path(caught.exception.manifest_path)
            saved = json.loads(manifest.read_text())
            self.assertEqual("FAILED_BROWNOUT", saved["status"])
            self.assertIn("JSONDecodeError", saved["error"])

    def test_critical_brownout_disables_swarm_and_safe_recovery_restores(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "autoflow.json"
            state = root / "storage-pressure.json"
            config.write_text(json.dumps({"swarm": {"enabled": True}, "other": 1}))
            entered = sync_brownout(config, state, critical=True)
            self.assertTrue(entered["active"])
            self.assertFalse(json.loads(config.read_text())["swarm"]["enabled"])
            recovered = sync_brownout(config, state, critical=False)
            self.assertFalse(recovered["active"])
            self.assertTrue(recovered["restored"])
            self.assertTrue(json.loads(config.read_text())["swarm"]["enabled"])

    def test_brownout_does_not_overwrite_runtime_config_changed_by_someone_else(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config = root / "autoflow.json"
            state = root / "storage-pressure.json"
            config.write_text(json.dumps({"swarm": {"enabled": True}, "other": 1}))
            sync_brownout(config, state, critical=True)
            changed = json.loads(config.read_text())
            changed["other"] = 2
            config.write_text(json.dumps(changed))
            recovered = sync_brownout(config, state, critical=False)
            self.assertFalse(recovered["restored"])
            self.assertEqual("CONFIG_CHANGED", recovered["restore_reason"])
            self.assertFalse(json.loads(config.read_text())["swarm"]["enabled"])

    def test_existing_gc_is_delegated_not_reimplemented(self):
        policy = self.policy()
        calls = []

        def fake_runner(argv, **kwargs):
            calls.append([str(x) for x in argv])
            return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")

        result = run_existing_gc(Path("/srv/logres"), policy, runner=fake_runner)
        self.assertEqual(3, len(result))
        joined = [" ".join(call) for call in calls]
        self.assertIn("/srv/logres/bin/logres-workspace-gc apply --limit 25", joined[0])
        self.assertIn("/srv/logres/bin/logres-worktree-gc --apply --age-hours 24", joined[1])
        self.assertIn("/srv/logres/bin/logres-preview-reaper --apply --age-hours 2", joined[2])

    def test_repository_policy_aligns_critical_disk_gate_and_maintenance_uses_guard(self):
        policy = load_policy(CONTROL_ROOT / "config" / "storage_retention.json")
        autoflow = json.loads((CONTROL_ROOT / "config" / "autoflow.default.json").read_text())
        self.assertEqual(
            float(autoflow["autonomy"]["min_free_disk_gib"]),
            float(policy["thresholds"]["critical_free_gib"]),
        )
        maintain = (CONTROL_ROOT / "bin" / "logres-maintain").read_text()
        self.assertIn("logres-storage-guard apply", maintain)
        self.assertNotIn("logres-storage-guard apply || true", maintain)
        self.assertNotIn("logres-workspace-gc apply", maintain)
        self.assertNotIn("logres-worktree-gc --apply", maintain)
        self.assertNotIn("tail -c 5242880", maintain)
        self.assertNotIn("logs/*.log", maintain)
        self.assertTrue({
            "control", "index", "artifacts", "recovery", "research", "src", "work"
        }.issubset(set(policy["protected_roots"])))
        direct_roots = {tier["root"] for tier in policy["retention_tiers"]}
        self.assertNotIn("tmp", direct_roots)
        log_tier = next(tier for tier in policy["retention_tiers"] if tier["root"] == "logs")
        self.assertNotIn("*.log", log_tier["patterns"])
        self.assertTrue(set(log_tier["patterns"]).issubset({
            "verify-farm-*.log", "finish-*.log", "preflight-*.log"
        }))


if __name__ == "__main__":
    unittest.main()
