import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "scripts/logres/logres_reconstruction_compiler.py"
BIN_PATH = REPO / "ops/logres-control-plane/bin/logres-reconstruct"

spec = importlib.util.spec_from_file_location("logres_reconstruction_compiler", MODULE_PATH)
compiler = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(compiler)


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def fact_hash(facts):
    return hashlib.sha256(canonical(facts).encode()).hexdigest()


def strong_transition():
    return {
        "id": "state-transition:11",
        "domain": "critical_state_transition",
        "authority": "CONFIRMED_GLOBAL_3_0_24_CLIENT_STATE_MACHINE",
        "classification": "evidence-known-not-implemented",
        "implementation_refs": [],
        "test_refs": [],
        "semantic_resolution": "NO_DIRECT_FUNCTION_BINDING",
        "evidence": {
            "index": 11,
            "from": "FIELD_SELECT",
            "to": "FIELD_INFO",
            "message": "S_GMCL_FIELD_SELECT_REQ",
            "trigger": "server field selection / field info request",
            "guard": None,
            "action": None,
            "source_evidence": "GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE",
            "bound_global_functions": [],
        },
    }


def strong_protocol():
    return {
        "id": "protocol:C_GMCL_CHAR_MOVE_REQ",
        "domain": "protocol_message",
        "authority": "CONFIRMED_GLOBAL_3_0_24_PROTOCOL_ID",
        "classification": "evidence-known-not-implemented",
        "implementation_refs": [],
        "test_refs": [],
        "semantic_resolution": "PROTOCOL_SCHEMA_ONLY",
        "evidence": {
            "name": "C_GMCL_CHAR_MOVE_REQ",
            "id": 123,
            "hex": "0x0000007b",
            "direction": "client_to_server",
            "top_level_schema_evidence": "GLOBAL_CONSTRUCTOR_SIGNATURE",
        },
    }


def weak_jp():
    return {
        "id": "jp-map-lineage:999_000_00001.mbn",
        "domain": "jp_map_lineage_reference",
        "authority": "CURRENT_JP_LINEAGE_REFERENCE_ONLY",
        "classification": "implementation-with-weaker-evidence",
        "implementation_refs": ["src/game/logres/field/Fake.ts"],
        "test_refs": [],
        "semantic_resolution": "NOT_HISTORICAL_GLOBAL_WITHOUT_PREDICATE",
        "evidence": {
            "base_id": "999_000_00001",
            "path": "999_000_00001.mbn",
        },
    }


def static_method():
    return {
        "id": "method:lfs::SomeClass::doThing",
        "domain": "lfs_method",
        "authority": "CONFIRMED_GLOBAL_3_0_24_STATIC_CLIENT",
        "classification": "evidence-known-not-implemented",
        "implementation_refs": [],
        "test_refs": [],
        "semantic_resolution": "STATIC_METHOD_EXISTENCE_ONLY",
        "evidence": {
            "class": "lfs::SomeClass",
            "method": "doThing",
        },
    }


def external():
    return {
        "id": "external-ceiling:00",
        "domain": "external_evidence_ceiling",
        "authority": "EXPLICIT_COMPLETENESS_LEDGER_CEILING",
        "classification": "externally-unrecoverable",
        "implementation_refs": [],
        "test_refs": [],
        "semantic_resolution": "TERMINAL_EXTERNAL_FACT",
        "evidence": {
            "text": "retired server fact",
            "terminal": True,
        },
    }


def make_closure(path: Path):
    facts = [
        strong_protocol(),
        weak_jp(),
        external(),
        static_method(),
        strong_transition(),
    ]
    payload = {
        "provenance": compiler.CLOSURE_PROVENANCE,
        "closure_id": "c" * 64,
        "facts_sha256": fact_hash(facts),
        "historical_authority": "Global 3.0.24 / 2017-05-25",
        "current_jp_role": "LINEAGE_REFERENCE_ONLY",
        "sources": {},
        "facts": facts,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def make_graph(path: Path, closure_path: Path):
    closure_sha = compiler.sha256_file(closure_path)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        create table knowledge_nodes(
          node_id text primary key,
          kind text not null,
          label text not null,
          provenance text not null,
          confidence real not null,
          artifact_path text,
          artifact_sha text,
          metadata_json text not null default '{}'
        );
        create table knowledge_edges(
          src text not null,
          dst text not null,
          relation text not null,
          confidence real not null,
          task_id text,
          metadata_json text not null default '{}',
          primary key(src,dst,relation)
        );
        """
    )
    artifact_id = f"artifact:{closure_sha}"
    nodes = [
        (
            artifact_id,
            "artifact",
            closure_path.name,
            "GLOBAL_RECOVERED",
            1.0,
            str(closure_path),
            closure_sha,
        ),
        (
            "discovery:172",
            "claim",
            "OMEGA exhaustive reconstruction closure completed",
            "GLOBAL_RECOVERED",
            1.0,
            str(closure_path),
            closure_sha,
        ),
        (
            f"task:{compiler.SOURCE_TASK}",
            "task",
            compiler.SOURCE_TASK,
            "CONTROL_PLANE",
            1.0,
            None,
            None,
        ),
        (
            "commit:ff8434a",
            "commit",
            "ff8434a",
            "GIT_EXACT_SHA",
            1.0,
            None,
            None,
        ),
    ]
    conn.executemany(
        """insert into knowledge_nodes(
             node_id,kind,label,provenance,confidence,artifact_path,artifact_sha
           ) values(?,?,?,?,?,?,?)""",
        nodes,
    )
    conn.executemany(
        """insert into knowledge_edges(
             src,dst,relation,confidence,task_id
           ) values(?,?,?,?,?)""",
        [
            (
                artifact_id,
                "discovery:172",
                "evidence_for",
                1.0,
                compiler.SOURCE_TASK,
            ),
            (
                "discovery:172",
                f"task:{compiler.SOURCE_TASK}",
                "supports",
                1.0,
                compiler.SOURCE_TASK,
            ),
            (
                f"task:{compiler.SOURCE_TASK}",
                "commit:ff8434a",
                "produced",
                1.0,
                compiler.SOURCE_TASK,
            ),
        ],
    )
    conn.commit()
    conn.close()
    return closure_sha


class ReconstructionCompilerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.closure_path = self.root / "closure.json"
        self.db_path = self.root / "control.sqlite"
        self.closure = make_closure(self.closure_path)
        self.closure_sha = make_graph(self.db_path, self.closure_path)

    def tearDown(self):
        self.temp.cleanup()

    def graph_bundle(self):
        conn = compiler.open_graph_readonly(self.db_path)
        try:
            return compiler.graph_provenance_bundle(
                conn,
                closure_path=self.closure_path,
                closure_sha256=self.closure_sha,
                closure_sources={},
            )
        finally:
            conn.close()

    def test_valid_compile_prioritizes_critical_transition(self):
        output = compiler.compile_packets(
            compiler.load_closure(self.closure_path),
            self.graph_bundle(),
            limit=2,
        )
        self.assertEqual(2, output["counts"]["packets"])
        self.assertEqual(
            "critical_state_transition",
            output["packets"][0]["source_fact"]["domain"],
        )
        self.assertEqual(
            "RECONSTRUCTED",
            output["packets"][0]["requested_claim_confidence"],
        )
        self.assertFalse(output["automation"]["control_db_writes"])
        self.assertFalse(output["automation"]["merge"])

    def test_packet_contains_exact_evidence_ids_scopes_tests_and_guardrails(self):
        output = compiler.compile_packets(
            compiler.load_closure(self.closure_path),
            self.graph_bundle(),
            fact_ids={"state-transition:11"},
            limit=1,
        )
        packet = output["packets"][0]
        ids = set(packet["evidence_node_ids"])
        self.assertIn("closure-fact:state-transition:11", ids)
        self.assertIn(f"artifact:{self.closure_sha}", ids)
        self.assertIn("discovery:172", ids)
        self.assertIn(f"task:{compiler.SOURCE_TASK}", ids)
        self.assertTrue(packet["file_scopes"])
        self.assertTrue(packet["acceptance_tests"])
        self.assertTrue(packet["do_not_infer"])
        self.assertTrue(
            any("retired-server" in item for item in packet["do_not_infer"])
        )

    def test_confidence_promotion_is_rejected(self):
        with self.assertRaises(compiler.CompilerError) as ctx:
            compiler.compile_packets(
                compiler.load_closure(self.closure_path),
                self.graph_bundle(),
                requested_confidence="CONFIRMED ORIGINAL",
                fact_ids={"state-transition:11"},
                limit=1,
            )
        self.assertIn("must request RECONSTRUCTED", str(ctx.exception))

    def test_weak_jp_external_and_static_only_facts_cannot_compile(self):
        for fact_id in (
            "jp-map-lineage:999_000_00001.mbn",
            "external-ceiling:00",
            "method:lfs::SomeClass::doThing",
        ):
            with self.subTest(fact_id=fact_id):
                with self.assertRaises(compiler.CompilerError):
                    compiler.compile_packets(
                        compiler.load_closure(self.closure_path),
                        self.graph_bundle(),
                        fact_ids={fact_id},
                        limit=1,
                    )

    def test_recursive_source_and_auto_mutation_are_rejected(self):
        output = compiler.compile_packets(
            compiler.load_closure(self.closure_path),
            self.graph_bundle(),
            fact_ids={"state-transition:11"},
            limit=1,
        )
        packet = copy.deepcopy(output["packets"][0])
        packet["source_task_id"] = "AUTO-RE-GAP-123"
        packet["automation"]["merge"] = True
        errors = compiler.validate_packet(packet)
        self.assertTrue(
            any("recursive AUTO-RE/UNBLOCK" in error for error in errors)
        )
        self.assertTrue(
            any("automatic mutation" in error for error in errors)
        )

    def test_graph_must_confirm_exact_closure_artifact(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "update knowledge_nodes set confidence=0.5 where node_id=?",
            (f"artifact:{self.closure_sha}",),
        )
        conn.commit()
        conn.close()
        with self.assertRaises(compiler.CompilerError) as ctx:
            self.graph_bundle()
        self.assertIn("below 0.90", str(ctx.exception))

    def test_compilation_does_not_mutate_control_database(self):
        before = self.db_path.read_bytes()
        conn = compiler.open_graph_readonly(self.db_path)
        try:
            bundle = compiler.graph_provenance_bundle(
                conn,
                closure_path=self.closure_path,
                closure_sha256=self.closure_sha,
                closure_sources={},
            )
            compiler.compile_packets(
                compiler.load_closure(self.closure_path),
                bundle,
                limit=2,
            )
        finally:
            conn.close()
        after = self.db_path.read_bytes()
        self.assertEqual(hashlib.sha256(before).hexdigest(), hashlib.sha256(after).hexdigest())

    def test_cli_compile_and_validate_are_json_only_and_non_mutating(self):
        output_path = self.root / "packets.json"
        run = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "compile",
                "--closure",
                str(self.closure_path),
                "--database",
                str(self.db_path),
                "--output",
                str(output_path),
                "--limit",
                "2",
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        payload = json.loads(output_path.read_text())
        self.assertEqual(2, payload["counts"]["packets"])

        valid = subprocess.run(
            [
                sys.executable,
                str(BIN_PATH),
                "validate",
                str(output_path),
            ],
            cwd=REPO,
            text=True,
            capture_output=True,
        )
        self.assertEqual(0, valid.returncode, valid.stdout + valid.stderr)
        self.assertEqual("PASS", json.loads(valid.stdout)["status"])

    def test_packet_limit_is_bounded(self):
        with self.assertRaises(compiler.CompilerError):
            compiler.compile_packets(
                compiler.load_closure(self.closure_path),
                self.graph_bundle(),
                limit=compiler.HARD_PACKET_LIMIT + 1,
            )


if __name__ == "__main__":
    unittest.main()
