#!/usr/bin/env python3
"""Build the evidence-bounded Global 3.0.24 critical runtime state machine."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

EXPECTED = {
    "C_GMCL_ACCOUNT_LOGIN_REQ": "0x740a055c",
    "C_GMCL_ACCOUNT_LOGIN_REQ_Response": "0x01888052",
    "C_GMCL_CHAR_CREATE_REQ": "0x1e6bde29",
    "C_GMCL_CHAR_CREATE_REQ_Response": "0x646507ef",
    "C_GMCL_CHAR_LOGIN_REQ": "0x24f8b2ea",
    "C_GMCL_CHAR_LOGIN_REQ_Response": "0x19aac5fc",
    "C_GMCL_FIELD_SELECT_REQ": "0x1001c0c8",
    "S_GMCL_FIELD_SELECT_REQ": "0x11734684",
    "C_GMCL_FIELD_INFO_REQ": "0x5789022a",
    "C_GMCL_FIELD_INFO_REQ_Response": "0xb032b4e3",
    "C_GMCL_ZONEIN_REQ": "0x8634bc61",
    "C_GMCL_ZONEIN_REQ_Response": "0xb7490c46",
    "S_GMCL_AREA_ENTER": "0x6dff0f05",
    "C_GMCL_CHAR_MOVE_REQ": "0x7d8ff367",
    "S_GMCL_CHAR_MOVE_REQ": "0x9d495842",
    "C_GMCL_CHAR_TALK_REQ": "0x53393da6",
    "C_GMCL_CHAR_TALK_REQ_Response": "0xd75a0bdf",
    "S_GMCL_NPC_APPEAR": "0x1b1ec5ec",
    "S_GMCL_ENEMY_APPEAR": "0xfe718a65",
    "C_GMCL_BATTLE_ENTRY_REQ": "0xfdff67d2",
    "C_GMCL_BATTLE_ENTRY_REQ_Response": "0x3228ac27",
    "S_GMCL_BATTLE_INITIALIZE": "0xdb83b305",
    "S_GMCL_BATTLE_BOUT_INITIALIZE": "0x3c9b8593",
    "C_GMCL_BATTLE_USE_SKILL_REQ": "0xd6d29a83",
    "C_GMCL_BATTLE_USE_SKILL_REQ_Response": "0xf06e5520",
    "S_GMCL_BATTLE_BOUT_EVENT_DROP": "0x4a890d9c",
    "S_GMCL_BATTLE_RESULT": "0x5b1ffeba",
    "S_GMCL_ITEM_INFO": "0xf503d3f0",
    "S_GMCL_QUEST_INFO_STATE_RESULT": "0x61a28538",
    "S_GMCL_QUEST_INFO_STATE_RETURN": "0xd5567b24",
}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def t(src, dst, trigger, *, message=None, guard=None, action=None, evidence, unresolved=None):
    row = {"from":src,"to":dst,"trigger":trigger,"evidence":evidence}
    if message: row["message"] = message
    if guard: row["guard"] = guard
    if action: row["action"] = action
    if unresolved: row["unresolved"] = unresolved
    return row

def build(protocol_path: Path):
    protocol=json.loads(protocol_path.read_text())
    idx={m["name"]:m for m in protocol["messages"]}
    for name, opcode in EXPECTED.items():
        if name not in idx:
            raise SystemExit(f"missing Global protocol procedure {name}")
        if idx[name]["opcode_hex"].lower()!=opcode:
            raise SystemExit(f"opcode mismatch {name}: {idx[name]['opcode_hex']} != {opcode}")
    states=[
        "TITLE","ACCOUNT_AUTH","TERMS_GATE","CHARACTER_LIST","GENDER_CREATE",
        "CHARACTER_LOGIN","PREBEGIN_INIT","FIELD_SELECT","FIELD_INFO","ZONEIN",
        "AREA_ACTIVE","FIELD_MOVEMENT","NPC_INTERACTION","ENCOUNTER_ELIGIBILITY",
        "BATTLE_ENTRY_PENDING","BATTLE_ENTRY_RETRY_WAIT","BATTLE_ACCEPTED",
        "BATTLE_INITIALIZING","BOUT_ACTIVE","BATTLE_RESULT","REWARD_PROJECTION",
        "FIELD_RETURN","ERROR_OR_EXTERNAL_AUTHORITY"
    ]
    transitions=[
        t("TITLE","ACCOUNT_AUTH","tap start / authentication start",
          evidence="GLOBAL_NATIVE_SCENE_AND_AUTH_SYMBOL_SURFACE"),
        t("ACCOUNT_AUTH","TERMS_GATE","account-login result NOT_AGREEMENT",
          message="C_GMCL_ACCOUNT_LOGIN_REQ_Response",guard="AccountLoginResult=3",
          action="ReleaseScene_AccountLogIn::onAuthRequireAgreement creates AgreementWebView",
          evidence="GLOBAL_DIRECT_GHIDRA_0x0205ed78"),
        t("ACCOUNT_AUTH","CHARACTER_LIST","account login accepted",
          message="C_GMCL_ACCOUNT_LOGIN_REQ_Response",
          guard="SUCCESS=1 or REAUTH_SUCCESS=2",
          evidence="GLOBAL_PROTOCOL_ENUM_PLUS_AUTHENTICATION_BEHAVIOR"),
        t("CHARACTER_LIST","PREBEGIN_INIT","character-list callback",
          action="set branch=1 if empty, branch=2 if non-empty; call GameInformation::initializeForPreBeginGame",
          evidence="GLOBAL_DIRECT_GHIDRA_0x0205f024"),
        t("PREBEGIN_INIT","GENDER_CREATE","login-scene branch 1",
          action="ReleaseScene_CharcterMake::create",
          evidence="GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478440"),
        t("PREBEGIN_INIT","CHARACTER_LOGIN","login-scene branch 2",
          action="ReleaseScene_CharacterLogin::create",
          evidence="GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478400"),
        t("PREBEGIN_INIT","TITLE","login-scene branch 4",
          action="ReleaseScene_Title::create",
          evidence="GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478450"),
        t("GENDER_CREATE","CHARACTER_LOGIN","character create success",
          message="C_GMCL_CHAR_CREATE_REQ_Response",guard="e_GmClCharCreateResult::SUCCESS=0",
          action="SceneManager::changeScene(ReleaseScene_CharacterLogin::create(), null transition)",
          evidence="GLOBAL_DIRECT_GHIDRA_0x02069078_PLUS_PLT_0x1478400"),
        t("CHARACTER_LOGIN","PREBEGIN_INIT","character login accepted",
          message="C_GMCL_CHAR_LOGIN_REQ_Response",
          guard="reply code in {1 SUCCESS,2 FORWARD,3 RECOVERY,4 SPAWN}",
          action="codes 1-4 enter accepted path; RECOVERY=3 additionally emits recovery event",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01e9d644"),
        t("CHARACTER_LOGIN","ERROR_OR_EXTERNAL_AUTHORITY","character login error",
          message="C_GMCL_CHAR_LOGIN_REQ_Response",
          guard="reply code outside 1..4; code 7 has distinct error handling",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01e9d644"),
        t("PREBEGIN_INIT","FIELD_SELECT","begin field bootstrap",
          message="C_GMCL_FIELD_SELECT_REQ",
          evidence="GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE"),
        t("FIELD_SELECT","FIELD_INFO","server field selection / field info request",
          message="S_GMCL_FIELD_SELECT_REQ",
          evidence="GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE"),
        t("FIELD_INFO","ZONEIN","field info resolved then zone-in",
          message="C_GMCL_ZONEIN_REQ",
          evidence="GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE"),
        t("ZONEIN","AREA_ACTIVE","server supplies authoritative area entry",
          message="S_GMCL_AREA_ENTER",
          action="construct lfs::AreaEnter NetworkObject and publish NetworkManager event",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01eb7590"),
        t("AREA_ACTIVE","FIELD_MOVEMENT","local path request",
          message="C_GMCL_CHAR_MOVE_REQ",
          action="SimpleAStar -> MovePathInitializer -> MoverComplyPath; server projects S_GMCL_CHAR_MOVE_REQ",
          evidence="GLOBAL_NATIVE_FIELD_EVIDENCE"),
        t("AREA_ACTIVE","NPC_INTERACTION","NPC appears / player talks",
          message="C_GMCL_CHAR_TALK_REQ",
          action="server talk response C_GMCL_CHAR_TALK_REQ_Response; Global timing constants 1.0s and 5.0s exist",
          evidence="GLOBAL_NATIVE_FIELD_AND_NPC_EVIDENCE",
          unresolved="exact assignment of the 1.0s/5.0s timers to request/response phases"),
        t("AREA_ACTIVE","ENCOUNTER_ELIGIBILITY","enemy symbol enters encounter radius",
          message="S_GMCL_ENEMY_APPEAR",
          action="client checks eligibility gates before requesting battle entry",
          evidence="GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE"),
        t("ENCOUNTER_ELIGIBILITY","BATTLE_ENTRY_PENDING","all client encounter gates pass",
          message="C_GMCL_BATTLE_ENTRY_REQ",
          evidence="GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE"),
        t("BATTLE_ENTRY_PENDING","BATTLE_ACCEPTED","battle-entry response accepted",
          message="C_GMCL_BATTLE_ENTRY_REQ_Response",guard="response code=1",
          action="entryAccepted=true",
          evidence="GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148"),
        t("BATTLE_ENTRY_PENDING","BATTLE_ENTRY_RETRY_WAIT","battle-entry response retry",
          message="C_GMCL_BATTLE_ENTRY_REQ_Response",guard="response code=2",
          action="retry wait exactly 1.0 second",
          evidence="GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148"),
        t("BATTLE_ENTRY_RETRY_WAIT","BATTLE_ENTRY_PENDING","retry delay elapsed",
          message="C_GMCL_BATTLE_ENTRY_REQ",
          evidence="GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE"),
        t("BATTLE_ACCEPTED","BATTLE_INITIALIZING","server initializes battle",
          message="S_GMCL_BATTLE_INITIALIZE",
          action="NetworkSession forwards BattleSystemUID into battle subsystem",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01ebaec0"),
        t("BATTLE_INITIALIZING","BOUT_ACTIVE","server initializes bout",
          message="S_GMCL_BATTLE_BOUT_INITIALIZE",
          action="BoutSystem/BoutSequencer/BoutEPManager become active projection path",
          evidence="GLOBAL_NATIVE_BATTLE_ARCHITECTURE"),
        t("BOUT_ACTIVE","BOUT_ACTIVE","player skill request / sequenced server events",
          message="C_GMCL_BATTLE_USE_SKILL_REQ",
          action="server-authoritative ordered battle event stream; client renders protocol projection",
          evidence="GLOBAL_PROTOCOL_AND_BATTLE_NATIVE_EVIDENCE"),
        t("BOUT_ACTIVE","BATTLE_RESULT","server battle result",
          message="S_GMCL_BATTLE_RESULT",
          action="NetworkSession projects t_BattleResultInfo into battle result processing",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01ebb04c"),
        t("BATTLE_RESULT","REWARD_PROJECTION","drop/item/quest result projection",
          message="S_GMCL_QUEST_INFO_STATE_RESULT",
          action="construct QuestInfoStateResult and dispatch to quest manager/event path; item/drop messages are server authored",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01ec21c4_PLUS_GLOBAL_BATTLE_EVIDENCE"),
        t("REWARD_PROJECTION","FIELD_RETURN","quest/result return projection",
          message="S_GMCL_QUEST_INFO_STATE_RETURN",
          action="construct QuestInfoStateReturn and dispatch to quest manager/event path",
          evidence="GLOBAL_DIRECT_GHIDRA_0x01ec263c"),
        t("FIELD_RETURN","AREA_ACTIVE","resume field runtime",
          action="ReleaseScene_GameField remains field scene; battle finish flow returns control after server-authored result/reward",
          evidence="GLOBAL_NATIVE_BATTLE_AND_FIELD_EVIDENCE",
          unresolved="exact retired-server post-battle warp/field payload values for every encounter"),
    ]
    return {
      "provenance":"CONFIRMED_GLOBAL_3_0_24_CRITICAL_STATE_MACHINE_WITH_EXPLICIT_SERVER_CEILINGS",
      "source":{"protocol_schema":str(protocol_path),"protocol_schema_sha256":sha256(protocol_path),
                "global_libgame_sha256":"bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f",
                "ghidra_project":"logres-global-3024-light"},
      "states":states,"transitions":transitions,
      "counts":{"states":len(states),"transitions":len(transitions),"bound_protocol_ids":len(EXPECTED)},
      "protocol_ids":EXPECTED,
      "direct_global_ghidra":{
        "account_login_update":"0x0205f4a0",
        "agreement_gate":"0x0205ed78",
        "character_list_callback":"0x0205f024",
        "recovery_login_callback":"0x0205f1b4",
        "character_create_response_scene":"0x02069078",
        "authentication_character_login_response":"0x01e9d644",
        "game_information_prebegin":"0x02121364",
        "game_information_begin_game":"0x02121624",
        "area_enter_handler":"0x01eb7590",
        "battle_entry_response_handler":"0x01eba148",
        "battle_initialize_handler":"0x01ebaec0",
        "battle_result_handler":"0x01ebb04c",
        "quest_result_handler":"0x01ec21c4",
        "quest_return_handler":"0x01ec263c",
      },
      "response_semantics":{
        "account_login":{"SUCCESS":1,"REAUTH_SUCCESS":2,"NOT_AGREEMENT":3,"DISALLOW":4,
                         "INVALID_SESSION_TOKEN":5,"CLIENT_VERSION_ERROR":6,"SUSPENDED":7},
        "character_create":{"SUCCESS":0,"DUPLICATION":1,"WORD_FILTER":2,"OTHER_ERR":3},
        "character_login":{"UNKNOWN":0,"SUCCESS":1,"FORWARD":2,"RECOVERY":3,"SPAWN":4,
                           "ERR_LOGOUT_NOW":5,"ERR_CHANNEL_IS_FULL":6,"ERR_WORLD_IS_FULL":7},
        "battle_entry":{"ACCEPTED":1,"RETRY_WAIT":2,"RETRY_SECONDS":1.0}
      },
      "guardrails":[
        "The recovered client proves client transitions and server message projections, not retired-server validation/persistence decisions.",
        "Current-JP schema/behavior is not used as authority for transitions whose Global schema changed.",
        "Login recovery branch state=3 has no direct scene factory in ReleaseScene_AccountLogIn::update; its later destination remains unresolved.",
        "Battle damage/stat/cooldown/EP/reward-roll formulas remain server-authority or separately unresolved evidence.",
        "Exact post-battle field/warp payload values remain external retired-server evidence."
      ]
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--protocol",type=Path,default=Path("/home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json"))
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    out=build(args.protocol)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["counts"],sort_keys=True))
if __name__=="__main__": main()
