import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

CONTROL_ROOT = Path(__file__).resolve().parents[1]
LIB = CONTROL_ROOT / "lib" / "logres_capacity.py"
SPEC = importlib.util.spec_from_file_location("logres_capacity", LIB)
capacity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capacity)


class CapacityTests(unittest.TestCase):
    def policy(self):
        return capacity.default_policy()

    def signals(self, **overrides):
        base = {
            "host": {
                "cpu_psi_avg10": 0.4,
                "memory_psi_avg10": 0.0,
                "io_psi_avg10": 0.1,
                "mem_available_ratio": 0.75,
                "load_per_cpu": 0.2,
            },
            "verifier": {"backlog": 1, "latency_seconds": 90.0},
            "queue": {"ready": 20, "independent_ready": 14, "oldest_ready_age_seconds": 300.0},
            "recent": {"failure_ratio": 0.05, "terminal_samples": 20, "integrations_last_hour": 4},
            "active": {"logical": 2},
            "devin": {
                "quota_known": True,
                "daily_remaining_ratio": 0.8,
                "weekly_remaining_ratio": 0.8,
                "cloud_session_limit": 6,
                "free_variants": 3,
                "on_demand_authorized": False,
            },
            "availability": {"copilot": False, "chatgpt": True, "research": True},
            "department_demand": {"Engineering": 8, "QA": 3, "Research": 2},
            "critical_department": "Engineering",
        }
        for key, value in overrides.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key].update(value)
            else:
                base[key] = value
        return base

    def test_conservative_profile_scales_to_twelve_logical_four_heavy(self):
        plan = capacity.plan_capacity(self.signals(), self.policy())
        self.assertEqual(12, plan["logical_workers"])
        self.assertEqual(4, plan["heavy_local_workers"])
        self.assertEqual(6, plan["lane_caps"]["devin_cloud"])
        self.assertEqual(0, plan["lane_caps"]["copilot"])
        self.assertLessEqual(plan["heavy_local_workers"], plan["lane_caps"]["local"])

    def test_high_host_pressure_downshifts_heavy_local_without_killing_cloud(self):
        signals = self.signals(host={
            "cpu_psi_avg10": 12.0,
            "memory_psi_avg10": 5.0,
            "io_psi_avg10": 9.0,
            "mem_available_ratio": 0.10,
            "load_per_cpu": 1.4,
        })
        plan = capacity.plan_capacity(signals, self.policy())
        self.assertEqual("high", plan["pressure"])
        self.assertLessEqual(plan["heavy_local_workers"], 1)
        self.assertLessEqual(plan["logical_workers"], 8)
        self.assertGreaterEqual(plan["lane_caps"]["devin_cloud"], 1)

    def test_unknown_free_devin_quota_is_not_treated_as_unlimited(self):
        plan = capacity.plan_capacity(
            self.signals(devin={"quota_known": False, "cloud_session_limit": 12}),
            self.policy(),
        )
        self.assertLessEqual(plan["lane_caps"]["devin_cloud"], 2)
        self.assertFalse(plan["spending"]["on_demand_authorized"])

    def test_low_and_critical_devin_quota_downshift_before_spending(self):
        low = capacity.plan_capacity(
            self.signals(devin={"daily_remaining_ratio": 0.10, "weekly_remaining_ratio": 0.10}),
            self.policy(),
        )
        critical = capacity.plan_capacity(
            self.signals(devin={"daily_remaining_ratio": 0.03, "weekly_remaining_ratio": 0.03}),
            self.policy(),
        )
        self.assertEqual(1, low["lane_caps"]["devin_cloud"])
        self.assertEqual(0, critical["lane_caps"]["devin_cloud"])
        self.assertFalse(critical["spending"]["allow_paid_fallback"])

    def test_verifier_saturation_reserves_verifier_capacity_and_reduces_fanout(self):
        plan = capacity.plan_capacity(
            self.signals(verifier={"backlog": 10, "latency_seconds": 1200.0}),
            self.policy(),
        )
        self.assertLess(plan["logical_workers"], 12)
        self.assertEqual(4, plan["lane_caps"]["verifier"])
        self.assertIn("verifier_saturated", plan["reasons"])

    def test_old_independent_queue_scales_up_only_when_factory_is_healthy(self):
        policy = self.policy()
        policy["logical_workers"]["target"] = 10
        plan = capacity.plan_capacity(self.signals(queue={"oldest_ready_age_seconds": 1200.0}), policy)
        self.assertEqual(12, plan["logical_workers"])
        blocked = capacity.plan_capacity(
            self.signals(verifier={"backlog": 9, "latency_seconds": 1000.0}), policy
        )
        self.assertLess(blocked["logical_workers"], 12)

    def test_failure_rate_downshifts_capacity(self):
        plan = capacity.plan_capacity(
            self.signals(recent={"failure_ratio": 0.4, "terminal_samples": 10, "integrations_last_hour": 2}),
            self.policy(),
        )
        self.assertLessEqual(plan["logical_workers"], 10)
        self.assertIn("recent_failure_rate", plan["reasons"])

    def test_department_allocations_sum_to_logical_capacity_and_expose_all_departments(self):
        plan = capacity.plan_capacity(self.signals(), self.policy())
        alloc = plan["departments"]
        self.assertEqual(plan["logical_workers"], sum(alloc.values()))
        self.assertEqual(
            {"Engineering", "Design", "Research", "QA", "Security", "Art", "Release"},
            set(alloc),
        )
        self.assertGreaterEqual(alloc["Engineering"], alloc["Art"])

    def test_runtime_overlays_raise_caps_without_enabling_disabled_paid_lanes(self):
        plan = capacity.plan_capacity(self.signals(), self.policy())
        autoflow = {
            "swarm": {"enabled": True, "max_workers": 6, "research_workers": 4, "implementation_dispatch_per_tick": 2},
            "copilot": {"max_active": 0, "max_queued": 0},
            "openai": {"budget_usd": 0.0, "max_active": 0, "max_active_hard": 0},
        }
        devin = {"router": {"enabled": True, "allow_paid": False, "workers": 2, "max_active": 2, "dispatch_per_tick": 2}}
        auto2, devin2 = capacity.build_runtime_overlays(autoflow, devin, plan)
        self.assertEqual(plan["logical_workers"], auto2["swarm"]["max_workers"])
        self.assertEqual(0, auto2["copilot"]["max_active"])
        self.assertEqual(0, auto2["openai"]["max_active_hard"])
        self.assertFalse(devin2["router"]["allow_paid"])
        self.assertEqual(plan["lane_caps"]["devin_cloud"], devin2["router"]["max_active"])
        self.assertEqual(plan["lane_caps"]["devin_cloud"], devin2["router"]["workers"])

    def test_execute_swarm_tick_uses_temporary_overlays_without_mutating_bases(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            control = root / "control"
            config = root / "config"
            scratch = root / "scratch"
            bin_dir = root / "bin"
            for path in (control, config, scratch, bin_dir):
                path.mkdir(parents=True, exist_ok=True)
            base_auto = {
                "swarm": {"enabled": True, "max_workers": 6, "research_workers": 4, "implementation_dispatch_per_tick": 2},
                "copilot": {"max_active": 0},
                "openai": {"max_active_hard": 0, "budget_usd": 0.0},
            }
            base_devin = {"router": {"enabled": True, "allow_paid": False, "workers": 2, "max_active": 2, "dispatch_per_tick": 2}}
            (control / "autoflow.json").write_text(json.dumps(base_auto))
            (config / "devin_workers.json").write_text(json.dumps(base_devin))
            (bin_dir / "logres-swarm").write_text("placeholder")
            plan = capacity.plan_capacity(self.signals(), self.policy())
            seen = {}

            class Result:
                returncode = 0
                stdout = '{"ok":true}'
                stderr = ''

            def runner(argv, **kwargs):
                seen["argv"] = list(argv)
                seen["env"] = dict(kwargs["env"])
                seen["autoflow"] = json.loads(Path(kwargs["env"]["LOGRES_AUTOFLOW_CONFIG"]).read_text())
                seen["devin"] = json.loads(Path(kwargs["env"]["LOGRES_DEVIN_WORKER_CONFIG"]).read_text())
                return Result()

            result = capacity.execute_swarm_tick(root, plan, runner=runner)
            self.assertEqual([str(bin_dir / "logres-swarm"), "tick"], seen["argv"])
            self.assertEqual(plan["logical_workers"], seen["autoflow"]["swarm"]["max_workers"])
            self.assertEqual(plan["lane_caps"]["devin_cloud"], seen["devin"]["router"]["max_active"])
            self.assertEqual(base_auto, json.loads((control / "autoflow.json").read_text()))
            self.assertEqual(base_devin, json.loads((config / "devin_workers.json").read_text()))
            self.assertEqual(0, result["returncode"])

    def test_policy_file_matches_required_initial_profile(self):
        raw = json.loads((CONTROL_ROOT / "config" / "capacity_policy.json").read_text())
        self.assertEqual(12, raw["logical_workers"]["target"])
        self.assertEqual(4, raw["heavy_local_workers"]["target"])
        self.assertFalse(raw["quota"]["allow_on_demand_default"])
        self.assertEqual(2, raw["quota"]["unknown_devin_cap"])


if __name__ == "__main__":
    unittest.main()
