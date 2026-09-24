from __future__ import annotations
import hashlib,json,sqlite3
from logres_mission_coverage import scan

REQUIRED_TEMPLATE={"title","work_type","priority","scopes","acceptance"}

def _template_valid(value):
    return (
      isinstance(value,dict)
      and REQUIRED_TEMPLATE.issubset(value)
      and isinstance(value.get("scopes"),list) and bool(value["scopes"])
      and isinstance(value.get("acceptance"),list) and bool(value["acceptance"])
    )

def _suggest(gap):
    kind=gap["gap_kind"]
    refs=gap.get("references",[])
    if kind=="EVIDENCE_CEILING":
        task=next((r for r in refs if r.get("type")=="task"),None)
        return {"check_type":"evidence_state","task_id":task.get("id") if task else None,
                "evidence_policy":"historical evidence required; never promote later-version inference",
                "template_allowed":False}
    if kind=="DEPENDENCY_BLOCKED":
        task=next((r for r in refs if r.get("type")=="task"),None)
        return {"check_type":"dependency_state","task_id":task.get("id") if task else None,
                "evidence_policy":"preserve existing dependency and evidence gates","template_allowed":False}
    if kind=="RUNNABLE_OR_ACTIVE":
        task=next((r for r in refs if r.get("type")=="task"),None)
        return {"check_type":"task_state","task_id":task.get("id") if task else None,
                "evidence_policy":"existing task authority","template_allowed":False}
    return {"check_type":"task_state","task_id":None,
            "evidence_policy":"implementation may proceed only from explicit scope and acceptance; historical claims remain evidence-gated",
            "template_allowed":True}

def compile_proposals(conn,templates=None):
    templates=templates or {}
    coverage=scan(conn,persist=False)
    proposals=[]
    for gap in coverage["gaps"]:
        suggested=_suggest(gap)
        template=templates.get(gap["objective_id"])
        emitted=template if suggested["template_allowed"] and _template_valid(template) else None
        proposal={
          "objective_id":gap["objective_id"],"title":gap["title"],
          "definition_of_done":gap["definition_of_done"],"state":gap["state"],
          "gap_kind":gap["gap_kind"],"references":gap.get("references",[]),
          "suggested_check":suggested,
          "task_template":emitted,
          "template_status":"READY" if emitted else (
             "FORBIDDEN_EVIDENCE_CEILING" if gap["gap_kind"] == "EVIDENCE_CEILING"
             else "EXISTING_WORK" if not suggested["template_allowed"]
             else "NEEDS_EXPLICIT_SCOPE_ACCEPTANCE"
          ),
        }
        raw=json.dumps(proposal,sort_keys=True,separators=(",",":"))
        proposal["fingerprint"]=hashlib.sha256(raw.encode()).hexdigest()
        proposals.append(proposal)
    return {"proposal_count":len(proposals),"proposals":proposals,
            "authority":"PROPOSAL_ONLY_NO_TASK_CREATION_NO_CONTRACT_MUTATION"}

def load_templates(path):
    data=json.loads(path.read_text())
    if not isinstance(data,dict):raise ValueError("template map must be an object")
    return data
