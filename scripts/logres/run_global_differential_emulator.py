#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any

PROVENANCE = "MUIUE_OFFLINE_GLOBAL_VS_RECONSTRUCTION_DIFFERENTIAL"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

FIXTURE_TS = r"""
import {
  LogresGlobalBehaviorTwin,
  serverAuthorityStub,
} from './src/game/logres/reverse/LogresGlobalBehaviorTwin'
import {
  ReconstructedLogresEncounterAuthority,
} from './src/game/logres/encounter/ReconstructedLogresEncounterAuthority'
import {
  ReconstructedLogresBattleEntryBridge,
} from './src/game/logres/encounter/ReconstructedLogresBattleEntryBridge'
import {
  resolveLogresGlobalMoveTarget,
} from './src/game/logres/field/LogresGlobalNativeFieldEvidence'
import {
  findReconstructedLogresFieldPath,
} from './src/game/logres/field/LogresFieldPathfinder'
import {
  completeReconstructedLogresDemoBattle,
} from './src/game/logres/battle/ReconstructedLogresDemoBattleLoop'

const stub = <T>(value:T) => serverAuthorityStub(value, 'differential fixture')
const eligible = () => ({
  globalEncounterAllowed: true,
  encounterEnabled: true,
  entryStateEligible: true,
  questAllowsEncounter: true,
  distanceEligible: true,
})
const tile = (col:number,row:number,extra:any={}) => ({
  col,row,prohibited:false,level:0,regionId:7,attribute:0,...extra,
})
const lookup = (tiles:any[]) => {
  const m = new Map(tiles.map(t => [`${t.col},${t.row}`, t]))
  return (col:number,row:number) => m.get(`${col},${row}`)
}

const moveTiles = [
  tile(0,0), tile(1,0), tile(2,0), tile(3,0),
  tile(4,0,{prohibited:true,regionId:9}),
]
const moveResolution = resolveLogresGlobalMoveTarget(
  moveTiles[0], moveTiles[4], lookup(moveTiles),
)
const movementTwin = new LogresGlobalBehaviorTwin({initialState:'AREA_ACTIVE'})
movementTwin.requestMove()

const cornerTiles = [
  tile(0,0),
  tile(1,0,{prohibited:true}),
  tile(0,1,{prohibited:true}),
  tile(1,1),
]
const cornerPath = findReconstructedLogresFieldPath(
  {col:0,row:0},{col:1,row:1},lookup(cornerTiles),
)

const retryTwin = new LogresGlobalBehaviorTwin({initialState:'AREA_ACTIVE'})
retryTwin.receiveEnemyAppear(stub({}))
retryTwin.requestBattleEntry()
retryTwin.receiveBattleEntry(stub(2))
const retryTwinBeforeElapsed = {
  state: retryTwin.state,
  trace: retryTwin.trace.map(x => ({
    from:x.from,to:x.to,message:x.message,event:x.event,
  })),
}
retryTwin.elapseBattleRetry(1)

const retryAuthority = new ReconstructedLogresEncounterAuthority({
  encounterKey:'diff-retry',areaRef:null,symbolRef:null,mapPosition:null,
  rawEntryState:null,eligibility:eligible(),
})
retryAuthority.createBattleEntryIntent()
retryAuthority.recordBattleEntryResponse({rawCode:2})
const retryActual = retryAuthority.snapshot()
let immediateRetryAllowed = false
let immediateRetryError:string|null = null
try {
  retryAuthority.createBattleEntryIntent()
  immediateRetryAllowed = true
} catch (error) {
  immediateRetryError = error instanceof Error ? error.message : String(error)
}

const acceptTwin = new LogresGlobalBehaviorTwin({initialState:'AREA_ACTIVE'})
acceptTwin.receiveEnemyAppear(stub({}))
acceptTwin.requestBattleEntry()
acceptTwin.receiveBattleEntry(stub(1))

const acceptAuthority = new ReconstructedLogresEncounterAuthority({
  encounterKey:'diff-accept',areaRef:null,symbolRef:null,mapPosition:null,
  rawEntryState:null,eligibility:eligible(),
})
acceptAuthority.createBattleEntryIntent()
acceptAuthority.recordBattleEntryResponse({rawCode:1})
const acceptActual = acceptAuthority.snapshot()

const bridgeAuthority = new ReconstructedLogresEncounterAuthority({
  encounterKey:'diff-bridge',areaRef:null,symbolRef:null,mapPosition:null,
  rawEntryState:null,eligibility:eligible(),
})
const bridge = new ReconstructedLogresBattleEntryBridge(bridgeAuthority)
bridge.requestEntry()
bridge.recordEntryResponse({rawCode:1})
const bridgeBeforeInit = {
  bridge: bridge.snapshot(),
  encounter: bridgeAuthority.snapshot(),
}
bridge.recordBattleInitialized({
  battleSystemRef:'diff-battle',
  battleKit:{
    weaponPanels:[],
    selectedWeaponSlot:null,
    currentEp:0,
    epCap:null,
  },
})
const bridgeAfterInit = {
  bridge: bridge.snapshot(),
  encounter: bridgeAuthority.snapshot(),
}

const rewardTwin = new LogresGlobalBehaviorTwin({initialState:'BOUT_ACTIVE'})
rewardTwin.receiveBattleResult(stub({}))
rewardTwin.receiveQuestResult(stub({}))
rewardTwin.receiveQuestReturn(stub({}))
rewardTwin.resumeField()

const rewardActual = completeReconstructedLogresDemoBattle()
const rewardRetry = completeReconstructedLogresDemoBattle(rewardActual.inventory)

console.log(JSON.stringify({
  movement:{
    expectedTwin:movementTwin.trace,
    targetResolution:moveResolution,
    cornerPath,
  },
  encounterRetry:{
    expectedTwinBeforeElapsed:retryTwinBeforeElapsed,
    expectedTwinAfterElapsedState:retryTwin.state,
    actual:retryActual,
    immediateRetryAllowed,
    immediateRetryError,
  },
  encounterAccept:{
    expectedTwinState:acceptTwin.state,
    actual:acceptActual,
  },
  bridge:{
    beforeInit:bridgeBeforeInit,
    afterInit:bridgeAfterInit,
  },
  reward:{
    expectedTwinState:rewardTwin.state,
    expectedTwinTrace:rewardTwin.trace,
    actual:rewardActual,
    retry:rewardRetry,
  },
}))
"""

def run_fixture(repo: Path) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".ts", dir=repo, delete=False
    ) as handle:
        handle.write(FIXTURE_TS)
        temp_path = Path(handle.name)
    try:
        proc = subprocess.run(
            [str(repo / "node_modules/.bin/tsx"), str(temp_path)],
            cwd=repo,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(proc.stdout)
    finally:
        temp_path.unlink(missing_ok=True)

def finding(
    id: str,
    domain: str,
    classification: str,
    score: float,
    summary: str,
    expected: Any,
    actual: Any,
    evidence: list[str],
) -> dict[str, Any]:
    return {
        "id": id,
        "domain": domain,
        "classification": classification,
        "evidence_score": score,
        "summary": summary,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
        "auto_fix_allowed": False,
        "auto_merge_allowed": False,
    }

def build(args: argparse.Namespace) -> dict[str, Any]:
    twin = json.loads(args.behavior_twin.read_text())
    binder = json.loads(args.asset_binder.read_text())
    fuzzer = json.loads(args.evidence_fuzzer.read_text())
    observed = run_fixture(args.repo)

    controller = (
        args.repo
        / "src/game/logres/field/controllers/LogresFieldEncounterController.ts"
    )
    controller_text = controller.read_text()
    controller_requests = "bridge.requestEntry()" in controller_text
    controller_records_response = "bridge.recordEntryResponse(" in controller_text
    controller_initializes = "bridge.recordBattleInitialized(" in controller_text

    findings: list[dict[str, Any]] = []

    move = observed["movement"]
    resolved = move["targetResolution"]
    move_pass = (
        resolved
        and resolved["usedFallback"] is True
        and resolved["resolved"]["col"] == 3
        and resolved["resolved"]["row"] == 0
        and move["cornerPath"] is None
    )
    findings.append(finding(
        "movement-global-fallback-and-collision",
        "movement_collision",
        "PASS" if move_pass else "IMPLEMENTATION_BUG",
        1.0,
        "Reconstruction applies recovered destination-to-source fallback and rejects diagonal corner cutting.",
        {
            "fallback": "requested blocked/wrong-region tile backs toward source to first valid same-region tile",
            "corner_cut": "blocked orthogonal neighbors reject diagonal path",
            "message": "C_GMCL_CHAR_MOVE_REQ",
        },
        {
            "targetResolution": resolved,
            "cornerPath": move["cornerPath"],
            "twinMessage": move["expectedTwin"][0].get("message"),
        },
        [
            "CONFIRMED_GLOBAL_3_0_24_NATIVE MovePathInitializer fallback",
            "GLOBAL_NATIVE_FIELD_EVIDENCE transition 14",
        ],
    ))

    retry = observed["encounterRetry"]
    retry_delay_pass = (
        retry["actual"]["lastResponseCode"] == 2
        and retry["actual"]["retryDelaySeconds"] == 1
        and retry["actual"]["entryAccepted"] is False
        and retry["expectedTwinBeforeElapsed"]["state"] == "BATTLE_ENTRY_RETRY_WAIT"
    )
    findings.append(finding(
        "battle-entry-retry-value",
        "encounter",
        "PASS" if retry_delay_pass else "IMPLEMENTATION_BUG",
        1.0,
        "Encounter authority records Global response code 2 as exactly one second of retry wait.",
        {"code": 2, "retrySeconds": 1.0},
        retry["actual"],
        [
            "GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148",
            "behavior twin exact rule battle_entry_retry_seconds=1.0",
        ],
    ))

    retry_guard_bug = retry["immediateRetryAllowed"] is True
    findings.append(finding(
        "battle-entry-retry-gate-enforcement",
        "encounter",
        "IMPLEMENTATION_BUG" if retry_guard_bug else "PASS",
        1.0,
        "A second entry request must not be issued until the recovered one-second retry wait has elapsed.",
        {
            "stateBeforeElapsed": "BATTLE_ENTRY_RETRY_WAIT",
            "nextAllowedAfter": "BATTLE_RETRY_DELAY_ELAPSED at exactly 1.0 second",
        },
        {
            "immediateRetryAllowed": retry["immediateRetryAllowed"],
            "error": retry["immediateRetryError"],
        },
        [
            "GLOBAL battle-entry gate order includes RETRY_WAIT_ELAPSED_AND_REQUEST_NOT_PENDING",
            "behavior twin transition 19 -> 20",
            "ReconstructedLogresEncounterAuthority runtime fixture",
        ],
    ))

    accept = observed["encounterAccept"]
    accept_pass = (
        accept["expectedTwinState"] == "BATTLE_ACCEPTED"
        and accept["actual"]["entryAccepted"] is True
        and accept["actual"]["lastResponseCode"] == 1
    )
    findings.append(finding(
        "battle-entry-accepted-code",
        "encounter",
        "PASS" if accept_pass else "IMPLEMENTATION_BUG",
        1.0,
        "Response code 1 maps to the distinct local entryAccepted state.",
        {"code": 1, "entryAccepted": True},
        accept["actual"],
        [
            "GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148",
            "behavior twin transition 18",
        ],
    ))

    bridge = observed["bridge"]
    bridge_pass = (
        bridge["beforeInit"]["bridge"]["phase"] == "entry-response-received"
        and bridge["beforeInit"]["bridge"]["launch"] is None
        and bridge["beforeInit"]["encounter"]["battleInitialized"] is False
        and bridge["afterInit"]["bridge"]["phase"] == "battle-ready"
        and bridge["afterInit"]["encounter"]["battleInitialized"] is True
    )
    findings.append(finding(
        "battle-entry-bridge-order",
        "battle_sequencing",
        "PASS" if bridge_pass else "IMPLEMENTATION_BUG",
        1.0,
        "Bridge API correctly keeps battle-entry response separate from authoritative battle initialization.",
        {
            "entryResponse": "does not initialize battle",
            "battleInitialize": "separate authoritative step",
        },
        bridge,
        [
            "behavior twin transitions 18/21",
            "ReconstructedLogresBattleEntryBridge runtime fixture",
        ],
    ))

    controller_bug = (
        controller_requests and controller_initializes and not controller_records_response
    )
    findings.append(finding(
        "playable-field-battle-entry-wiring",
        "battle_sequencing",
        "IMPLEMENTATION_BUG" if controller_bug else "PASS",
        1.0,
        "Playable field wiring must not jump from local entry request directly to battle initialization.",
        {
            "required": [
                "C_GMCL_BATTLE_ENTRY_REQ",
                "C_GMCL_BATTLE_ENTRY_REQ_Response code 1/2",
                "S_GMCL_BATTLE_INITIALIZE",
            ],
            "retryRule": "code 2 waits exactly 1.0 second before re-request",
        },
        {
            "requestEntryCall": controller_requests,
            "recordEntryResponseCall": controller_records_response,
            "recordBattleInitializedCall": controller_initializes,
            "source": str(controller),
            "sourceSha256": sha256_file(controller),
        },
        [
            "behavior twin transitions 17-21",
            "GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE",
            "LogresFieldEncounterController source wiring",
        ],
    ))

    reward = observed["reward"]
    reward_order_pass = (
        reward["expectedTwinState"] == "AREA_ACTIVE"
        and reward["actual"]["flow"]["phase"] == "field-return-ready"
        and reward["actual"]["rewardApplied"] is True
        and reward["actual"]["inventory"]["revision"] == 1
    )
    findings.append(finding(
        "battle-result-reward-field-return-order",
        "reward_projection",
        "INTENTIONAL_SERVER_STUB" if reward_order_pass else "IMPLEMENTATION_BUG",
        0.95,
        "Reconstruction preserves result -> reward -> field-return ordering, but reward identifiers/content are explicitly local because retired-server payloads are unrecovered.",
        {
            "highLevelStates": [
                "BATTLE_RESULT",
                "REWARD_PROJECTION",
                "FIELD_RETURN",
                "AREA_ACTIVE",
            ],
            "dynamicRewardPayload": "external evidence ceiling",
        },
        {
            "phase": reward["actual"]["flow"]["phase"],
            "rewardApplied": reward["actual"]["rewardApplied"],
            "inventory": reward["actual"]["inventory"],
        },
        [
            "behavior twin transitions 24-27",
            "behavior twin guardrail: reward rolls/persistence exact payloads remain external ceilings",
            "ReconstructedLogresDemoBattleLoop runtime fixture",
        ],
    ))

    idempotent = (
        reward["retry"]["rewardApplied"] is False
        and reward["retry"]["inventory"]["revision"] == 1
    )
    findings.append(finding(
        "reconstruction-local-reward-idempotency",
        "reward_projection",
        "UNKNOWN",
        0.55,
        "The local reconstructed grant is idempotent, but exact retired-Global reward grant/idempotency semantics are not established.",
        {"historicalBehavior": "UNRESOLVED"},
        {
            "localIdempotent": idempotent,
            "retryRewardApplied": reward["retry"]["rewardApplied"],
            "revision": reward["retry"]["inventory"]["revision"],
        },
        [
            "ReconstructedLogresDemoBattleLoop local grant behavior",
            "behavior twin external evidence ceiling for persistence/reward rolls",
        ],
    ))

    vertical = binder["vertical_slice"]
    exact_map = vertical["field_map"].get("exact_global_packages", [])
    exact_battle = vertical["battle"].get("exact_global_packages", [])
    resource_pass = bool(exact_map and exact_battle)
    findings.append(finding(
        "critical-resource-binding",
        "resource_bindings",
        "PASS" if resource_pass else "EVIDENCE_GAP",
        1.0,
        "Recovered Global field and battle package identities are bound to the vertical-slice evidence graph.",
        {
            "field": "map-002/002_000_00001.mbn",
            "battle": "Battle.mbn",
        },
        {
            "fieldPackages": exact_map,
            "battlePackages": exact_battle,
            "rolesWithDirectBindings": binder["counts"]["vertical_roles_with_direct_bindings"],
        },
        [
            f"asset binder sha256={sha256_file(args.asset_binder)}",
            "CONFIRMED_GLOBAL_RESOURCE_EXACT_BYTES_LINEAGE",
        ],
    ))

    classifications = Counter(row["classification"] for row in findings)
    divergences = [row for row in findings if row["classification"] != "PASS"]

    return {
        "provenance": PROVENANCE,
        "offline_only": True,
        "historical_facts_created": False,
        "sources": {
            "behavior_twin": {
                "path": str(args.behavior_twin),
                "sha256": sha256_file(args.behavior_twin),
                "provenance": twin["provenance"],
            },
            "asset_binder": {
                "path": str(args.asset_binder),
                "sha256": sha256_file(args.asset_binder),
                "provenance": binder["provenance"],
            },
            "evidence_fuzzer": {
                "path": str(args.evidence_fuzzer),
                "sha256": sha256_file(args.evidence_fuzzer),
                "provenance": fuzzer["provenance"],
            },
        },
        "fixture": {
            "runner": "node_modules/.bin/tsx",
            "repo": str(args.repo),
            "uses_actual_reconstruction_authorities": True,
            "uses_live_server": False,
        },
        "counts": {
            "checks": len(findings),
            "divergences": len(divergences),
            "classifications": dict(sorted(classifications.items())),
            "fuzzer_cases_available": fuzzer["coverage"]["total_cases"],
        },
        "findings": findings,
        "divergences": divergences,
        "implementation_packets": [
            {
                "id": "DIFF-FIX-BATTLE-ENTRY-BOUNDARY",
                "classification": "IMPLEMENTATION_BUG",
                "scope": [
                    "src/game/logres/field/controllers/LogresFieldEncounterController.ts",
                    "src/game/logres/encounter/ReconstructedLogresEncounterAuthority.ts",
                ],
                "acceptance": [
                    "Playable field must not initialize battle immediately after requestEntry().",
                    "Response code 1 must set entryAccepted before battle initialization.",
                    "Response code 2 must block another entry request until exactly 1.0 second elapses.",
                    "No retired-server payload or response outcome may be invented; use an explicit reconstructed/server stub at the boundary.",
                ],
                "auto_apply": False,
                "auto_merge": False,
            }
        ] if controller_bug or retry_guard_bug else [],
        "guardrails": [
            "Differential findings never auto-fix, auto-merge or auto-deploy.",
            "Server-authored payload differences remain intentional stubs or evidence gaps unless Global evidence directly constrains the client behavior.",
            "Presentation differences are not upgraded to gameplay bugs without a behavior/resource predicate.",
            "Unknown retired-server semantics remain UNKNOWN rather than being filled from current JP.",
        ],
    }

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, default=Path.cwd())
    root = Path("/home/ubuntu/logres/artifacts")
    p.add_argument("--behavior-twin", type=Path, default=root/"global3024-behavior-twin-20260924.json")
    p.add_argument("--asset-binder", type=Path, default=root/"global-asset-behavior-bindings-20260924.json")
    p.add_argument("--evidence-fuzzer", type=Path, default=root/"global3024-evidence-fuzzer-20260924.json")
    p.add_argument("--output", required=True, type=Path)
    return p.parse_args()

def main() -> int:
    args = parse_args()
    result = build(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["counts"], sort_keys=True))
    for row in result["divergences"]:
        print(f"{row['classification']} {row['id']}: {row['summary']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
