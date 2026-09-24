import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_chaos_cert import certify, run_probes


class ChaosCertificationTests(unittest.TestCase):
    def test_executable_sandbox_probes_all_pass(self):
        probes = run_probes()

        self.assertGreaterEqual(len(probes), 5)
        self.assertTrue(all(probe.passed for probe in probes))
        names = {probe.name for probe in probes}
        self.assertTrue(
            {
                "sqlite_writer_lock_retry",
                "route_semantic_dedupe",
                "research_frontier_dedupe",
                "resource_broker_fallback",
                "supervisor_single_effect",
            }.issubset(names)
        )

    def test_certification_is_shadow_only_and_hashed(self):
        repo = Path("/home/ubuntu/logres/src/awakened-realms")
        with tempfile.TemporaryDirectory() as td:
            payload = certify(
                repo=repo,
                artifact_root=Path(td),
                shadow=True,
            )
            artifact = Path(payload["artifact_path"])
            stored = json.loads(artifact.read_text())

        cert_hash = stored.pop("certification_sha256")
        canonical = json.dumps(
            stored,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        self.assertEqual(
            hashlib.sha256(canonical).hexdigest(),
            cert_hash,
        )
        self.assertEqual("PASS", payload["verdict"])
        self.assertEqual("shadow", payload["mode"])
        self.assertTrue(payload["sandbox_only"])
        self.assertFalse(payload["production_control_db_opened"])
        self.assertFalse(payload["authority"]["merge"])
        self.assertFalse(payload["authority"]["deploy"])
        self.assertFalse(payload["authority"]["push"])
        self.assertFalse(payload["authority"]["production_db_write"])

    def test_non_shadow_certification_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(
                ValueError,
                "shadow-only",
            ):
                certify(
                    repo=Path(
                        "/home/ubuntu/logres/src/awakened-realms"
                    ),
                    artifact_root=Path(td),
                    shadow=False,
                )

    def test_implementation_has_no_production_control_db_path(self):
        text = (
            CONTROL_ROOT / "lib" / "logres_chaos_cert.py"
        ).read_text()

        self.assertNotIn(
            "/home/ubuntu/logres/control/control.sqlite",
            text,
        )
        self.assertNotIn("integration_queue", text)
        self.assertNotIn("git push", text)
        self.assertNotIn("merge-train", text)

    def test_supervisor_schedules_only_shadow_certification(self):
        supervisor = (
            CONTROL_ROOT / "lib" / "logres_supervisor.py"
        ).read_text()

        self.assertIn('"chaos_cert"', supervisor)
        self.assertIn('"logres-chaos-cert"', supervisor)
        self.assertIn('"--shadow"', supervisor)
        self.assertIn('"--quiet"', supervisor)


if __name__ == "__main__":
    unittest.main()
