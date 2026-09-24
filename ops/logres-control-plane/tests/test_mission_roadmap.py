import json
import sqlite3
import sys
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
CONTROL_ROOT = TEST_DIR.parent
LIB_DIR = CONTROL_ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_goal_contract import load_contracts
from logres_goal_executor import validate_execution_template
from logres_mission import load_config, objective_status


MISSION_CONFIG = CONTROL_ROOT / "config" / "mission.default.json"
CONTRACT_CONFIG = CONTROL_ROOT / "config" / "milestone_contracts.json"


def make_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        create table tasks(id text primary key,status text);
        create table milestones(
          id text primary key,
          title text not null,
          sort_order integer not null,
          status text not null,
          definition_of_done text not null,
          created_at text not null,
          updated_at text not null
        );
        """
    )
    return conn


class MissionRoadmapTests(unittest.TestCase):
    def test_every_leaf_objective_has_source_controlled_coverage(self):
        conn = make_db()
        load_config(conn, MISSION_CONFIG)
        missing = [
            str(row[0])
            for row in conn.execute(
                """
                select o.id
                  from mission_objectives o
                 where not exists(
                       select 1 from mission_objectives c where c.parent_id=o.id
                 )
                   and not exists(
                       select 1 from mission_links l where l.objective_id=o.id
                 )
                 order by o.id
                """
            )
        ]
        self.assertEqual([], missing)

    def test_existing_milestone_status_is_preserved(self):
        conn = make_db()
        conn.execute(
            """insert into milestones(
                 id,title,sort_order,status,definition_of_done,created_at,updated_at
               ) values(?,?,?,?,?,?,?)""",
            ("DEMO-0.2", "old", 20, "ACTIVE", "old", "original-created", "old"),
        )
        load_config(conn, MISSION_CONFIG)
        row = conn.execute(
            "select title,sort_order,status,created_at from milestones where id='DEMO-0.2'"
        ).fetchone()
        self.assertEqual("Authentic playable presentation", row[0])
        self.assertEqual(20, row[1])
        self.assertEqual("ACTIVE", row[2])
        self.assertEqual("original-created", row[3])

    def test_future_milestones_are_planned_in_order(self):
        conn = make_db()
        load_config(conn, MISSION_CONFIG)
        rows = list(
            conn.execute(
                "select id,sort_order,status from milestones order by sort_order"
            )
        )
        self.assertEqual(
            [
                "DEMO-0.2",
                "DEMO-0.3",
                "SYSTEMS-0.4",
                "CONTENT-0.5",
                "FIDELITY-0.6",
                "RELEASE-1.0",
            ],
            [str(row[0]) for row in rows],
        )
        self.assertEqual(
            ["PLANNED"] * 5,
            [str(row[2]) for row in rows[1:]],
        )

    def test_demo03_completed_leaf_tasks_count_as_partial_progress_without_closing_milestone(self):
        conn = make_db()
        links = {
            "UI_RUNTIME": "MISSION-UI-RUNTIME-001",
            "AUDIO_RUNTIME": "MISSION-AUDIO-RUNTIME-001",
            "ANDROID_CLIENT": "MISSION-ANDROID-CLIENT-INTEGRATE-002",
            "NPC_DIALOGUE": "MISSION-NPC-DIALOGUE-001",
            "QUESTS": "MISSION-QUESTS-001",
        }
        for task_id in links.values():
            conn.execute(
                "insert into tasks(id,status) values(?, 'DONE')",
                (task_id,),
            )

        load_config(conn, MISSION_CONFIG)

        for objective_id, task_id in links.items():
            configured = list(
                conn.execute(
                    """select milestone_id,task_id,gate_type
                         from mission_links
                        where objective_id=?
                        order by gate_type,milestone_id,task_id""",
                    (objective_id,),
                )
            )
            self.assertEqual(2, len(configured), objective_id)
            self.assertTrue(
                any(
                    row[0] == "DEMO-0.3"
                    and row[1] is None
                    and row[2] == "required"
                    for row in configured
                ),
                objective_id,
            )
            self.assertTrue(
                any(
                    row[0] is None
                    and row[1] == task_id
                    and row[2] == "supporting"
                    for row in configured
                ),
                objective_id,
            )

            status = objective_status(conn, objective_id)
            self.assertEqual("IN_PROGRESS", status.state, objective_id)
            self.assertEqual(50.0, status.progress_percent, objective_id)

        self.assertEqual(
            "UNCOVERED",
            objective_status(conn, "PROGRESSION").state,
        )

        conn.execute(
            "update milestones set status='DONE' where id='DEMO-0.3'"
        )
        for objective_id in links:
            status = objective_status(conn, objective_id)
            self.assertEqual("COMPLETE", status.state, objective_id)
            self.assertEqual(100.0, status.progress_percent, objective_id)

    def test_every_roadmap_milestone_has_a_contract(self):
        mission = json.loads(MISSION_CONFIG.read_text())
        contracts = load_contracts(CONTRACT_CONFIG)
        missing = [
            item["id"]
            for item in mission["milestones"]
            if item["id"] not in contracts["milestones"]
        ]
        self.assertEqual([], missing)

    def test_all_executable_templates_satisfy_goal_executor_schema(self):
        contracts = load_contracts(CONTRACT_CONFIG)
        checked = 0
        for milestone_id, milestone in contracts["milestones"].items():
            for criterion in milestone["criteria"]:
                template = criterion.get("task_template")
                if template is None:
                    continue
                normalized = validate_execution_template(template)
                self.assertTrue(normalized["scopes"], milestone_id)
                self.assertTrue(normalized["acceptance"], milestone_id)
                if criterion["check"]["type"] == "task_state":
                    self.assertTrue(
                        str(criterion["check"].get("task_id") or "").strip(),
                        f"{milestone_id}/{criterion['id']}",
                    )
                checked += 1
        self.assertGreaterEqual(checked, 19)

    def test_demo02_map_identity_uses_sealed_evidence_ceiling(self):
        contracts = load_contracts(CONTRACT_CONFIG)
        criterion = next(
            item
            for item in contracts["milestones"]["DEMO-0.2"]["criteria"]
            if item["id"] == "millennium-tree-map-identity"
        )
        self.assertEqual("artifact", criterion["check"]["type"])
        self.assertEqual(
            "artifacts/tutorial-map-id-global3024-evidence-ceiling-20260924.json",
            criterion["check"]["path"],
        )
        self.assertEqual(
            "c98879a0024143020581f395952c1804c7c796947a50fe2909765fa1ac7f00c7",
            criterion["check"]["sha256"],
        )
        self.assertNotIn("task_template", criterion)

    def test_future_milestones_keep_current_demo_first(self):
        conn = make_db()
        load_config(conn, MISSION_CONFIG)
        row = conn.execute(
            """select id from milestones
               where status not in ('DONE','RESOLVED','SUPERSEDED','CANCELLED')
               order by sort_order,id limit 1"""
        ).fetchone()
        self.assertEqual("DEMO-0.2", row[0])


if __name__ == "__main__":
    unittest.main()
