import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace

REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "scripts/logres/build_logres_truth_kernel.py"
BIN_PATH = REPO / "ops/logres-control-plane/bin/logres-truth"

spec = importlib.util.spec_from_file_location("build_logres_truth_kernel", MODULE_PATH)
truth = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(truth)


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def make_omega(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table claims(
          claim_id text primary key,
          claim_key text not null,
          domain text not null,
          version_scope text not null,
          provenance_grade text not null,
          authority_rank integer not null,
          payload_sha256 text not null,
          payload_json text not null,
          source_fact_id text,
          implementation_status text,
          historical_claim integer not null
        );
        create table artifacts(
          artifact_id text primary key,
          path text not null,
          sha256 text not null,
          bytes integer,
          provenance text,
          role text not null
        );
        create table claim_evidence(
          claim_id text not null,
          artifact_id text not null,
          evidence_role text not null,
          evidence_path text not null,
          evidence_sha256 text not null,
          primary key(claim_id,artifact_id,evidence_role)
        );
        create table contradictions(
          task_id text primary key,
          status text not null,
          rationale text,
          winner_authorities_json text not null,
          winner_claims_json text not null,
          loser_claims_json text not null,
          external_ceilings_json text not null,
          payload_sha256 text not null
        );
        create table external_ceilings(
          ceiling_id text primary key,
          text text not null,
          source_fact_id text not null
        );
        """
    )

    artifact_rows = [
        ("sha256:" + "a" * 64, "/evidence/global.json", "a" * 64, 1, "GLOBAL_DIRECT", "global"),
        ("sha256:" + "b" * 64, "/evidence/jp.json", "b" * 64, 1, "JP_LINEAGE_SUPPORTED", "jp"),
        ("sha256:" + "c" * 64, "/evidence/implementation.ts", "c" * 64, 1, "CURRENT_CANONICAL_RECONSTRUCTION", "implementation"),
    ]
    conn.executemany(
        "insert into artifacts values(?,?,?,?,?,?)",
        artifact_rows,
    )

    def insert_claim(
        claim_id,
        claim_key,
        domain,
        scope,
        grade,
        rank,
        payload,
        fact_id,
        historical,
        artifact_sha,
    ):
        payload_json = canonical(payload)
        payload_sha = digest_text(payload_json)
        conn.execute(
            """insert into claims(
                 claim_id,claim_key,domain,version_scope,provenance_grade,
                 authority_rank,payload_sha256,payload_json,source_fact_id,
                 implementation_status,historical_claim
               ) values(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                claim_id,
                claim_key,
                domain,
                scope,
                grade,
                rank,
                payload_sha,
                payload_json,
                fact_id,
                "covered",
                historical,
            ),
        )
        artifact_id = "sha256:" + artifact_sha
        artifact_path = conn.execute(
            "select path from artifacts where artifact_id=?",
            (artifact_id,),
        ).fetchone()[0]
        conn.execute(
            "insert into claim_evidence values(?,?,?,?,?)",
            (
                claim_id,
                artifact_id,
                "test",
                artifact_path,
                artifact_sha,
            ),
        )

    insert_claim(
        "fact:global",
        "shared:key",
        "critical_state_transition",
        truth.GLOBAL_SCOPE,
        "GLOBAL_DIRECT",
        0,
        {"id": "global", "value": "historical"},
        "shared-fact",
        1,
        "a" * 64,
    )
    insert_claim(
        "fact:jp",
        "shared:key",
        "jp_map_lineage_reference",
        truth.CURRENT_JP_SCOPE,
        "JP_LINEAGE_SUPPORTED",
        4,
        {"id": "jp", "value": "current"},
        "jp-only-fact",
        0,
        "b" * 64,
    )
    insert_claim(
        "fact:implementation",
        "shared:key",
        "implementation_link",
        truth.IMPLEMENTATION_SCOPE,
        "IMPLEMENTATION_VERIFIED",
        5,
        {"id": "implementation", "value": "reconstruction"},
        "shared-fact",
        0,
        "c" * 64,
    )

    tie = {
        "task_id": "G17-TUT-001",
        "status": "UNRESOLVED_SAME_AUTHORITY_TIE",
        "rationale": "two GLOBAL_BINARY_DERIVED claims disagree",
        "winner_authorities_json": "[]",
        "winner_claims_json": "[]",
        "loser_claims_json": json.dumps([
            {"artifact_sha": "a" * 64},
            {"artifact_sha": "b" * 64},
        ]),
        "external_ceilings_json": "[]",
        "payload_sha256": "d" * 64,
    }
    conn.execute(
        """insert into contradictions(
             task_id,status,rationale,winner_authorities_json,
             winner_claims_json,loser_claims_json,
             external_ceilings_json,payload_sha256
           ) values(:task_id,:status,:rationale,:winner_authorities_json,
                    :winner_claims_json,:loser_claims_json,
                    :external_ceilings_json,:payload_sha256)""",
        tie,
    )
    conn.execute(
        "insert into external_ceilings values(?,?,?)",
        (
            "ceiling:server",
            "Retired server validation and dynamic reward payloads are externally unrecoverable.",
            "external-ceiling:00",
        ),
    )
    conn.commit()
    conn.close()


def make_graph(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        """create table knowledge_nodes(
             node_id text primary key,
             kind text not null,
             label text not null,
             provenance text not null,
             confidence real not null,
             artifact_path text,
             artifact_sha text,
             metadata_json text not null default '{}'
           )"""
    )
    for sha, label in (
        ("a" * 64, "global evidence"),
        ("b" * 64, "JP evidence"),
        ("c" * 64, "implementation evidence"),
    ):
        conn.execute(
            """insert into knowledge_nodes(
                 node_id,kind,label,provenance,confidence,
                 artifact_path,artifact_sha,metadata_json
               ) values(?,?,?,?,?,?,?,?)""",
            (
                "artifact:" + sha,
                "artifact",
                label,
                "TEST",
                1.0,
                "/evidence/" + label.replace(" ", "_"),
                sha,
                "{}",
            ),
        )
    conn.commit()
    conn.close()


def make_manifest(path: Path, omega_path: Path, graph_path: Path):
    value = {
        "provenance": truth.PROVENANCE,
        "truth_kernel_id": "e" * 64,
        "omega_database": {
            "path": str(omega_path),
            "sha256": truth.sha256_file(omega_path),
        },
        "provenance_graph": {
            "path": str(graph_path),
        },
    }
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return value


class TruthKernelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.omega = self.root / "omega.sqlite"
        self.graph = self.root / "control.sqlite"
        self.manifest = self.root / "truth.json"
        make_omega(self.omega)
        make_graph(self.graph)
        make_manifest(self.manifest, self.omega, self.graph)

    def tearDown(self):
        self.temp.cleanup()

    def query(self, **kwargs):
        omega = truth.open_ro(self.omega)
        graph = truth.open_ro(self.graph)
        try:
            return truth.resolve_query(
                omega,
                graph,
                **kwargs,
            )
        finally:
            omega.close()
            graph.close()

    def test_global_claim_resolves_strongest_with_evidence_and_graph_node(self):
        result = self.query(
            mode="claim",
            value="shared:key",
            target="global",
            minimum_grade="GLOBAL_BINARY_DERIVED",
            limit=20,
        )
        self.assertEqual("RESOLVED", result["status"])
        self.assertEqual("GLOBAL_DIRECT", result["strongest_claim"]["provenance_grade"])
        self.assertEqual(truth.GLOBAL_SCOPE, result["strongest_claim"]["version_scope"])
        self.assertEqual("a" * 64, result["evidence"][0]["evidence_sha256"])
        self.assertEqual(
            "artifact:" + "a" * 64,
            result["provenance_graph_nodes"][0]["node_id"],
        )

    def test_jp_only_fact_never_backfills_historical_global(self):
        result = self.query(
            mode="fact",
            value="jp-only-fact",
            target="global",
            limit=20,
        )
        self.assertEqual("UNRESOLVED", result["status"])
        self.assertIsNone(result["strongest_claim"])
        self.assertEqual([], result["claims"])
        self.assertIn(
            "Current JP is not substituted",
            result["unresolved_ceiling"]["reason"],
        )

    def test_confidence_promotion_fails_closed(self):
        result = self.query(
            mode="fact",
            value="jp-only-fact",
            target="current-jp",
            minimum_grade="GLOBAL_DIRECT",
            limit=20,
        )
        self.assertEqual("REJECTED_CONFIDENCE_PROMOTION", result["status"])
        self.assertEqual("GLOBAL_DIRECT", result["required_grade"])
        self.assertEqual("JP_LINEAGE_SUPPORTED", result["supported_grade"])

    def test_any_target_preserves_scopes_instead_of_collapsing_versions(self):
        result = self.query(
            mode="claim",
            value="shared:key",
            target="any",
            limit=20,
        )
        self.assertEqual("RESOLVED", result["status"])
        self.assertEqual(
            {
                truth.GLOBAL_SCOPE,
                truth.CURRENT_JP_SCOPE,
                truth.IMPLEMENTATION_SCOPE,
            },
            set(result["scoped_results"]),
        )
        self.assertEqual("GLOBAL_DIRECT", result["strongest_claim"]["provenance_grade"])

    def test_contradiction_query_preserves_same_authority_tie(self):
        omega = truth.open_ro(self.omega)
        try:
            result = truth.contradiction_query(omega, "G17-TUT-001")
        finally:
            omega.close()
        self.assertEqual("RESOLVED", result["status"])
        self.assertEqual(
            "UNRESOLVED_SAME_AUTHORITY_TIE",
            result["contradiction"]["status"],
        )
        self.assertEqual([], result["contradiction"]["winner_authorities"])
        self.assertEqual([], result["contradiction"]["winner_claims"])

    def test_ceiling_search_returns_terminal_server_ceiling(self):
        omega = truth.open_ro(self.omega)
        try:
            rows = truth.relevant_ceilings(
                omega,
                "retired server reward",
                limit=3,
            )
        finally:
            omega.close()
        self.assertEqual(1, len(rows))
        self.assertEqual("ceiling:server", rows[0]["ceiling_id"])
        self.assertGreater(rows[0]["token_hits"], 0)

    def test_stats_are_machine_readable_and_version_scoped(self):
        omega = truth.open_ro(self.omega)
        try:
            stats = truth.stats_query(omega)
        finally:
            omega.close()
        self.assertEqual("RESOLVED", stats["status"])
        self.assertEqual(3, stats["claims"])
        self.assertEqual(3, stats["claim_evidence"])
        self.assertEqual(1, stats["external_ceilings"])
        self.assertEqual(1, stats["contradictions"]["status_counts"]["UNRESOLVED_SAME_AUTHORITY_TIE"])
        self.assertEqual(1, stats["version_scopes"][truth.GLOBAL_SCOPE])
        self.assertEqual(1, stats["version_scopes"][truth.CURRENT_JP_SCOPE])
        self.assertEqual(1, stats["version_scopes"][truth.IMPLEMENTATION_SCOPE])

    def test_cli_outputs_json_and_uses_exit_two_for_confidence_rejection(self):
        command = [
            sys.executable,
            str(BIN_PATH),
            "--manifest",
            str(self.manifest),
            "--omega-db",
            str(self.omega),
            "--graph-db",
            str(self.graph),
            "fact",
            "jp-only-fact",
            "--target",
            "current-jp",
            "--minimum-grade",
            "GLOBAL_DIRECT",
        ]
        run = subprocess.run(
            command,
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(2, run.returncode, run.stdout + run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual("REJECTED_CONFIDENCE_PROMOTION", payload["status"])

        ok = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "--manifest",
                str(self.manifest),
                "--omega-db",
                str(self.omega),
                "--graph-db",
                str(self.graph),
                "fact",
                "shared-fact",
                "--target",
                "global",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, ok.returncode, ok.stdout + ok.stderr)
        self.assertEqual("RESOLVED", json.loads(ok.stdout)["status"])

    def test_manifest_hash_tampering_is_rejected(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["omega_database"]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest))

        with self.assertRaises(truth.TruthError) as ctx:
            truth.verify_manifest(
                truth.load_json(self.manifest),
                omega_db=self.omega,
                graph_db=self.graph,
            )
        self.assertIn("hash mismatch", str(ctx.exception))

    def test_queries_do_not_mutate_omega_or_graph_databases(self):
        omega_before = hashlib.sha256(self.omega.read_bytes()).hexdigest()
        graph_before = hashlib.sha256(self.graph.read_bytes()).hexdigest()

        self.query(
            mode="search",
            value="shared",
            target="any",
            limit=20,
        )

        self.assertEqual(
            omega_before,
            hashlib.sha256(self.omega.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            graph_before,
            hashlib.sha256(self.graph.read_bytes()).hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
