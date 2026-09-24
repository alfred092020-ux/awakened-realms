#!/usr/bin/env python3
import importlib.util
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("verify_release_candidate.py")
SPEC = importlib.util.spec_from_file_location("release_verify", SCRIPT)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class ReleaseCandidateVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "-C", str(self.repo), "init", "-q"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "config", "user.name", "Test"],
            check=True,
        )
        (self.repo / "x").write_text("x\n")
        subprocess.run(["git", "-C", str(self.repo), "add", "x"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-q", "-m", "base"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "branch", "feat/logres-reconstruction"],
            check=True,
        )
        self.sha = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True
        ).strip()

        self.db = self.root / "control.sqlite"
        c = sqlite3.connect(self.db)
        c.executescript(
            """
            create table milestones(
              id text primary key,title text,sort_order integer,status text,
              definition_of_done text,created_at text,updated_at text
            );
            create table milestone_certificates(
              id integer primary key autoincrement,
              milestone_id text not null,
              integration_sha text not null,
              contract_fingerprint text not null,
              status text not null,
              artifact_path text not null,
              artifact_sha256 text not null,
              created_at text not null
            );
            create table verification(
              ref text,sha text,mode text,status text,duration_sec real,
              ran_at text,details text
            );
            """
        )
        self.required = ["DEMO-0.2", "FIDELITY-0.6"]
        for index, mid in enumerate(self.required, start=1):
            c.execute(
                "insert into milestones values(?,?,?,?,?,?,?)",
                (
                    mid,
                    mid,
                    index * 10,
                    "DONE",
                    "",
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                ),
            )
        c.execute(
            "insert into milestones values(?,?,?,?,?,?,?)",
            (
                "RELEASE-1.0",
                "Release",
                70,
                "PLANNED",
                "",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        self.certs = []
        for mid in self.required:
            cert_path = self.root / f"{mid}.json"
            cert_payload = {
                "milestone_id": mid,
                "integration_sha": self.sha,
                "status": "PASS",
                "valid": True,
            }
            cert_path.write_text(json.dumps(cert_payload))
            cert_sha = MOD.sha256_file(cert_path)
            cur = c.execute(
                """insert into milestone_certificates(
                     milestone_id,integration_sha,contract_fingerprint,status,
                     artifact_path,artifact_sha256,created_at
                   ) values(?,?,?,?,?,?,?)""",
                (
                    mid,
                    self.sha,
                    f"fp-{mid}",
                    "PASS",
                    str(cert_path),
                    cert_sha,
                    "2026-01-01T00:00:00+00:00",
                ),
            )
            self.certs.append(
                {
                    "certificate_id": cur.lastrowid,
                    "milestone_id": mid,
                    "integration_sha": self.sha,
                    "contract_fingerprint": f"fp-{mid}",
                    "status": "PASS",
                    "artifact_path": str(cert_path),
                    "artifact_sha256": cert_sha,
                }
            )
        c.execute(
            "insert into verification values(?,?,?,?,?,?,?)",
            (
                self.sha,
                self.sha,
                "full-e2e",
                "PASS",
                10.0,
                "2026-01-01T00:00:00+00:00",
                "test",
            ),
        )
        c.commit()
        c.close()

        self.apk = self.root / "app.apk"
        self.apk.write_bytes(b"apk-bytes")
        self.apk_sha = MOD.sha256_file(self.apk)

        self.checkpoint = self.root / "checkpoint.json"
        self.checkpoint.write_text(
            json.dumps(
                {
                    "schema": MOD.CHECKPOINT_SCHEMA,
                    "source": {"sha": self.sha},
                    "verification": {"status": "PASS", "mode": "full-e2e"},
                    "apk": {
                        "path": str(self.apk),
                        "sha256": self.apk_sha,
                        "bytes": self.apk.stat().st_size,
                        "signature_verified": True,
                    },
                }
            )
        )
        self.checkpoint_sha = MOD.sha256_file(self.checkpoint)

        self.manifest = self.root / "release.json"
        self.write_manifest()

    def tearDown(self):
        self.tmp.cleanup()

    def write_manifest(self, **overrides):
        payload = {
            "schema": MOD.SCHEMA,
            "source": {"sha": self.sha},
            "verification": {"status": "PASS", "mode": "full-e2e"},
            "apk": {
                "path": str(self.apk),
                "sha256": self.apk_sha,
                "bytes": self.apk.stat().st_size,
            },
            "checkpoint_manifest": {
                "path": str(self.checkpoint),
                "sha256": self.checkpoint_sha,
            },
            "milestone_certificates": self.certs,
        }
        payload.update(overrides)
        self.manifest.write_text(json.dumps(payload))

    def verify(self):
        return MOD.verify_candidate(
            self.manifest, repo=self.repo, control_db=self.db, require_current=True
        )

    def test_valid_exact_current_candidate_passes(self):
        result = self.verify()
        self.assertEqual("PASS", result["status"])
        self.assertEqual(self.sha, result["sha"])
        self.assertEqual(self.required, result["prerequisite_milestones"])

    def test_stale_sha_fails_closed(self):
        self.write_manifest(source={"sha": "a" * 40})
        with self.assertRaisesRegex(MOD.ReleaseCandidateError, "stale"):
            self.verify()

    def test_tampered_apk_fails_closed(self):
        self.apk.write_bytes(b"tampered")
        with self.assertRaisesRegex(MOD.ReleaseCandidateError, "hash mismatch"):
            self.verify()

    def test_missing_prerequisite_certificate_fails_closed(self):
        self.write_manifest(milestone_certificates=self.certs[:-1])
        with self.assertRaisesRegex(MOD.ReleaseCandidateError, "certificate set mismatch"):
            self.verify()

    def test_nonpass_checkpoint_fails_closed(self):
        payload = json.loads(self.checkpoint.read_text())
        payload["verification"]["status"] = "FAIL"
        self.checkpoint.write_text(json.dumps(payload))
        self.write_manifest(
            checkpoint_manifest={
                "path": str(self.checkpoint),
                "sha256": MOD.sha256_file(self.checkpoint),
            }
        )
        with self.assertRaisesRegex(MOD.ReleaseCandidateError, "not full-e2e PASS"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
