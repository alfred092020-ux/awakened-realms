from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib, json, time

HIGH_RISK_PREFIXES=("ops/logres-control-plane/","server/","src/battle/","src/persistence/","android/")
UI_PREFIXES=("src/ui/","src/components/","public/","assets/")

@dataclass(frozen=True)
class VerificationPlan:
    risk:str; lanes:tuple[str,...]; heavy_slots:int; reasons:tuple[str,...]
    def to_dict(self):
        d=asdict(self); d["lanes"]=list(self.lanes); d["reasons"]=list(self.reasons); return d

def risk_plan(paths, *, cpu_count=8, load=0.0, memory_free_ratio=1.0, heavy_cap=4):
    paths=tuple(sorted(set(str(p) for p in paths)))
    high=any(p.startswith(HIGH_RISK_PREFIXES) for p in paths)
    ui=bool(paths) and all(p.startswith(UI_PREFIXES) for p in paths)
    risk="high" if high else ("low" if ui else "medium")
    lanes=("changed","focused","build","e2e","exact-sha") if risk=="high" else (("changed","focused","build","exact-sha") if risk=="medium" else ("changed","focused","build"))
    cpu_headroom=max(0.0,1.0-float(load)/max(1,int(cpu_count)))
    pressure=min(cpu_headroom,max(0.0,min(1.0,float(memory_free_ratio))))
    slots=max(1,min(int(heavy_cap),int(max(1,int(cpu_count))//2),1+int(pressure*3)))
    return VerificationPlan(risk,lanes,slots,(f"paths={len(paths)}",f"cpu_headroom={cpu_headroom:.2f}",f"memory_free={memory_free_ratio:.2f}"))

def strategy_fingerprint(task_id, strategy, environment, failure):
    normalized=" ".join(str(failure).lower().split())
    material={"task":str(task_id),"strategy":str(strategy),"environment":str(environment),"failure":normalized}
    return hashlib.sha256(json.dumps(material,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def retry_decision(*, prior_fingerprints, task_id, strategy, environment, failure, transient=False):
    fp=strategy_fingerprint(task_id,strategy,environment,failure)
    repeated=fp in set(prior_fingerprints)
    if repeated: return {"retry":False,"fingerprint":fp,"action":"diagnose-change-one-variable"}
    return {"retry":bool(transient),"fingerprint":fp,"action":"retry-once" if transient else "diagnose"}

def speculative_receipt_valid(receipt, *, new_base_sha, changed_paths):
    if receipt.get("base_sha")==new_base_sha: return True
    covered=set(receipt.get("paths") or ()); changed=set(changed_paths or ())
    return covered.isdisjoint(changed) and bool(receipt.get("independent",False))

def stage_receipt(stage, *, task_id, artifact=None, expected_seconds=None, status="RUNNING", now=None):
    return {"stage":stage,"task_id":task_id,"status":status,"heartbeat_epoch":float(time.time() if now is None else now),"artifact":artifact,"expected_seconds":expected_seconds}

def authority_chain(builder, verifier, integrator, observer):
    roles=(builder,verifier,integrator,observer)
    distinct=len(set(roles))==4
    return {"builder":builder,"verifier":verifier,"integrator":integrator,"runtime_observer":observer,"independent":distinct,"eligible":distinct}

def operator_intent_wins(current_epoch, candidate_epoch):
    return float(candidate_epoch)>=float(current_epoch)
