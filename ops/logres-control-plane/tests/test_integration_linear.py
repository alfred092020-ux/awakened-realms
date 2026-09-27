import json
import sqlite3
import sys
import time
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_integration import (
    ensure_schema,
    list_intents,
    list_proposals,
    register_target,
    set_capabilities,
    upsert_binding,
)
from logres_integration_linear import observe_issue, plan_task_sync, project_task


class LinearAdapterTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        ensure_schema(self.conn)
        self._brain_schema()
        self._seed_task()

    def tearDown(self):
        self.conn.close()

    def _brain_schema(self):
        self.conn.executescript(
            """
            create table tasks(
              id text primary key, priority integer, lane text, title text,
              status text, branch text, owner text, note text, updated_at text
            );
            create table task_metadata(
              task_id text primary key, milestone text, work_type text,
              concurrency_key text, expected_minutes integer,
              evidence_policy text, created_at text, updated_at text
            );
            create table task_acceptance(
              task_id text, ordinal integer, criterion text,
              primary key(task_id,ordinal)
            );
            create table brain_task_leases(
              task_id text primary key, chat_id text, progress integer,
              lease_until_epoch real, branch text
            );
            create table evidence_assertions(
              id integer primary key, task_id text, confidence text, claim text
            );
            create table integration_queue(
              task_id text, sha text, status text,
              primary key(task_id,sha)
            );
            """
        )

    def _seed_task(self):
        long_title = "Linear adapter task " + ("x" * 260)
        self.conn.execute(
            "insert into tasks values(?,?,?,?,?,?,?,?,datetime('now'))",
            (
                "TASK-1", 0, "integrations", long_title, "ACTIVE",
                "worker/example", "worker", "private note must not project",
            ),
        )
        self.conn.execute(
            "insert into task_metadata values(?,?,?,?,?,?,datetime('now'),datetime('now'))",
            (
                "TASK-1", "brain-plugin-integration", "implementation",
                "linear", 90, "Evidence first",
            ),
        )
        for ordinal, criterion in enumerate(
            [
                "Create deterministic issue projections.",
                "Preserve Brain authority. " + ("detail " * 1600),
            ],
            start=1,
        ):
            self.conn.execute(
                "insert into task_acceptance values(?,?,?)",
                ("TASK-1", ordinal, criterion),
            )
        self.conn.execute(
            "insert into brain_task_leases values(?,?,?,?,?)",
            ("TASK-1", "owner-chat", 40, time.time() + 3600, "worker/example"),
        )
        self.conn.execute(
            "insert into evidence_assertions(task_id,confidence,claim) values(?,?,?)",
            ("TASK-1", "CONFIRMED", "evidence stays authoritative"),
        )

    def _target(self, *, enabled=True):
        return register_target(
            self.conn,
            provider="linear",
            target_key="logres",
            enabled=enabled,
            purpose="bounded Brain task projection",
            write_policy={
                "managed_fields": ["title", "description", "priority", "project", "labels"]
            },
            metadata={
                "team": "LOG",
                "project": "Logres Reconstruction",
                "labels": ["Brain", "Autonomy"],
            },
        )

    def _capability(self, chat_id="sync-chat"):
        set_capabilities(
            self.conn,
            chat_id=chat_id,
            capabilities=["linear.issue.write"],
            expires_at_epoch=time.time() + 3600,
            target_key="logres",
        )

    def test_projection_is_deterministic_bounded_and_linear_compatible(self):
        self._target()
        first = project_task(self.conn, "TASK-1", "logres")
        second = project_task(self.conn, "TASK-1", "logres")
        self.assertEqual(first, second)
        self.assertEqual(first["projection_hash"], second["projection_hash"])
        self.assertLessEqual(len(first["create_payload"]["title"]), 200)
        self.assertLessEqual(len(first["create_payload"]["description"]), 8000)
        self.assertEqual(1, first["create_payload"]["priority"])
        self.assertEqual("LOG", first["create_payload"]["team"])
        self.assertEqual("Logres Reconstruction", first["create_payload"]["project"])
        self.assertEqual(["Autonomy", "Brain"], first["create_payload"]["labels"])
        self.assertEqual("Logres Reconstruction", first["managed_fields"]["project"])
        self.assertEqual(["Autonomy", "Brain"], first["managed_fields"]["labels"])
        self.assertEqual(
            {"title", "description", "priority", "team", "project", "labels"},
            set(first["create_payload"]),
        )
        self.assertNotIn("private note", json.dumps(first["create_payload"]))

    def test_create_intent_is_idempotent_for_same_projection(self):
        self._target()
        self._capability()
        first = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        second = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("INTENT_CREATED", first["status"])
        self.assertEqual("issue.create", first["operation"])
        self.assertEqual(first["intent"]["id"], second["intent"]["id"])
        self.assertEqual(1, len(list_intents(self.conn, provider="linear")))
        self.assertEqual("linear.issue.write", first["intent"]["required_capability"])

    def test_existing_binding_plans_update_only_when_projection_changed(self):
        self._target()
        self._capability()
        projection = project_task(self.conn, "TASK-1", "logres")
        upsert_binding(
            self.conn,
            provider="linear",
            canonical_entity_type="brain_task",
            canonical_entity_id="TASK-1",
            provider_entity_type="issue",
            provider_entity_id="LOG-42",
            logical_slot="logres",
            projected_hash="old-projection",
            observed_hash="old-observed",
        )
        result = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("INTENT_CREATED", result["status"])
        self.assertEqual("issue.update", result["operation"])
        self.assertEqual("LOG-42", result["intent"]["payload"]["id"])
        self.assertEqual("Logres Reconstruction", result["intent"]["payload"]["project"])
        self.assertEqual(["Autonomy", "Brain"], result["intent"]["payload"]["labels"])
        self.assertEqual(projection["projection_hash"], result["intent"]["projection_hash"])

        upsert_binding(
            self.conn,
            provider="linear",
            canonical_entity_type="brain_task",
            canonical_entity_id="TASK-1",
            provider_entity_type="issue",
            provider_entity_id="LOG-42",
            logical_slot="logres",
            projected_hash=projection["projection_hash"],
            observed_hash="observed",
        )
        noop = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("IN_SYNC", noop["status"])

    def test_disabled_target_and_missing_capability_create_no_intents(self):
        self._target(enabled=False)
        disabled = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("TARGET_DISABLED", disabled["status"])
        self.assertEqual([], list_intents(self.conn, provider="linear"))

        self._target(enabled=True)
        missing = plan_task_sync(
            self.conn, "TASK-1", "logres", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("MISSING_CAPABILITY", missing["status"])
        self.assertEqual([], list_intents(self.conn, provider="linear"))

        set_capabilities(
            self.conn, chat_id="expired-chat",
            capabilities=["linear.issue.write"],
            expires_at_epoch=time.time() - 1, target_key="logres",
        )
        expired = plan_task_sync(
            self.conn, "TASK-1", "logres",
            chat_id="expired-chat", now_epoch=time.time(),
        )
        self.assertEqual("MISSING_CAPABILITY", expired["status"])
        self.assertEqual([], list_intents(self.conn, provider="linear"))

    def _authority_snapshot(self):
        return {
            "task": tuple(self.conn.execute(
                "select * from tasks where id='TASK-1'"
            ).fetchone()),
            "lease": tuple(self.conn.execute(
                "select * from brain_task_leases where task_id='TASK-1'"
            ).fetchone()),
            "evidence": tuple(self.conn.execute(
                "select * from evidence_assertions where task_id='TASK-1'"
            ).fetchone()),
            "queue": list(self.conn.execute("select * from integration_queue")),
        }

    def test_managed_external_drift_creates_idempotent_proposal_only(self):
        self._target()
        projection = project_task(self.conn, "TASK-1", "logres")
        before = self._authority_snapshot()
        observed = dict(projection["managed_fields"])
        observed["labels"] = ["Human-edited"]
        observed["assignee"] = "someone@example.com"

        first = observe_issue(
            self.conn, "TASK-1", "logres", provider_entity_id="LOG-42", observed=observed
        )
        second = observe_issue(
            self.conn, "TASK-1", "logres", provider_entity_id="LOG-42", observed=observed
        )
        self.assertEqual("PROPOSAL_CREATED", first["status"])
        self.assertEqual(first["proposal"]["id"], second["proposal"]["id"])
        proposals = list_proposals(self.conn, provider="linear")
        self.assertEqual(1, len(proposals))
        self.assertEqual("MANAGED_FIELD_DRIFT", proposals[0]["change_type"])
        self.assertEqual(before, self._authority_snapshot())

    def test_unmanaged_external_edits_do_not_create_proposals(self):
        self._target()
        projection = project_task(self.conn, "TASK-1", "logres")
        observed = dict(projection["managed_fields"])
        observed["assignee"] = "human@example.com"
        observed["state"] = "Done"
        result = observe_issue(
            self.conn, "TASK-1", "logres", provider_entity_id="LOG-42", observed=observed
        )
        self.assertEqual("IN_SYNC", result["status"])
        self.assertEqual([], list_proposals(self.conn, provider="linear"))

    def test_missing_target_projection_is_bounded_non_write_result(self):
        result = plan_task_sync(
            self.conn, "TASK-1", "missing", chat_id="sync-chat", now_epoch=time.time()
        )
        self.assertEqual("TARGET_MISSING", result["status"])
        self.assertEqual([], list_intents(self.conn, provider="linear"))


if __name__ == "__main__":
    unittest.main()
