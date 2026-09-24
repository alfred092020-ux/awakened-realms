import json,sqlite3,sys,unittest
from pathlib import Path
TEST_DIR=Path(__file__).resolve().parent
CONTROL_ROOT=TEST_DIR.parent
sys.path.insert(0,str(CONTROL_ROOT/"lib"))
from logres_mission_coverage import load_completion_manifest,scan

MANIFEST_PATH=CONTROL_ROOT/"config"/"completion_manifest.json"

class ProjectCompletionManifestTests(unittest.TestCase):
 def db(self):
  c=sqlite3.connect(":memory:"); c.row_factory=sqlite3.Row
  c.executescript("""create table mission_objectives(id text primary key,parent_id text,title text,definition_of_done text,sort_order integer);
  create table mission_links(objective_id text,milestone_id text,task_id text,gate_type text);
  create table tasks(id text primary key,status text,title text,note text);
  create table milestones(id text primary key,status text,title text,definition_of_done text);""")
  return c
 def note(self,category,represented=()):
  return json.dumps({"completion_coverage":{category:{"represented_ids":list(represented)}}},sort_keys=True)
 def test_manifest_is_versioned_finite_and_bounded(self):
  manifest=load_completion_manifest(MANIFEST_PATH)
  self.assertEqual("logres-project-completion-manifest-v1",manifest["schema"])
  self.assertEqual("2026-09-24.1",manifest["version"])
  self.assertEqual("d4449fcbfeae55a73c2a57ac38f823c29afbaf15",manifest["base_integration_sha"])
  self.assertIn("new manifest version",manifest["evidence_policy"])
  self.assertEqual({"MAP_CONTENT","ACTOR_CONTENT","COMBAT_CONTENT","ITEM_CONTENT","QUEST_CONTENT"},set(manifest["objectives"]))
  for category in manifest["categories"].values():
   self.assertTrue(category["targets"])
   for item in category["targets"].values():
    if item["disposition"]=="required": self.assertTrue(item["provenance_class"])
    else: self.assertTrue(item.get("evidence_ceiling") or item.get("exclusion_reason"))
 def test_five_done_umbrella_tasks_without_stable_ids_cannot_certify_content_completion(self):
  c=self.db()
  items=[("MAP_CONTENT","maps_regions"),("ACTOR_CONTENT","actors_npcs"),("COMBAT_CONTENT","combat_content"),("ITEM_CONTENT","items_equipment"),("QUEST_CONTENT","quests")]
  for n,(objective_id,_category) in enumerate(items,1):
   c.execute("insert into mission_objectives values(?,?,?, ?,?)",(objective_id,None,objective_id,"done",n))
   c.execute("insert into tasks values(?,?,?,?)",(f"T{n}","DONE",objective_id,""))
   c.execute("insert into mission_links values(?,null,?,'required')",(objective_id,f"T{n}"))
  r=scan(c,manifest_path=MANIFEST_PATH)
  self.assertEqual(5,r["gap_count"])
  self.assertTrue(all(gap["gap_kind"]=="DECLARED_CONTENT_GAP" for gap in r["gaps"]))
  self.assertTrue(all(summary["missing_count"]>=1 for summary in r["content_completion"].values()))
 def test_one_placeholder_category_does_not_allow_full_completion(self):
  c=self.db()
  items=[
   ("MAP_CONTENT","maps_regions",self.note("maps_regions",["placeholder-map"])),
   ("ACTOR_CONTENT","actors_npcs",self.note("actors_npcs",["reconstructed-millennium-tree-guide"])),
   ("COMBAT_CONTENT","combat_content",self.note("combat_content",["special-skill"])),
   ("ITEM_CONTENT","items_equipment",self.note("items_equipment",["reconstructed-tutorial-weapon"])),
   ("QUEST_CONTENT","quests",self.note("quests",["quest-start-win-battle"])),
  ]
  for n,(objective_id,_category,note) in enumerate(items,1):
   c.execute("insert into mission_objectives values(?,?,?, ?,?)",(objective_id,None,objective_id,"done",n))
   c.execute("insert into tasks values(?,?,?,?)",(f"T{n}","DONE",objective_id,note))
   c.execute("insert into mission_links values(?,null,?,'required')",(objective_id,f"T{n}"))
  r=scan(c,manifest_path=MANIFEST_PATH)
  self.assertEqual(1,r["gap_count"])
  self.assertEqual(["placeholder-map"],r["content_completion"]["maps_regions"]["undeclared_represented_ids"])
  self.assertEqual(4,r["counts"]["COMPLETE"])
if __name__=="__main__":unittest.main()
