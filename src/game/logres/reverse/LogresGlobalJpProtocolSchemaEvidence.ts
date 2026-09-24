export const LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_PROVENANCE =
  'GLOBAL_3_0_24_PROTOCOL_AUTHORITY_WITH_BOUNDED_CURRENT_JP_LINEAGE' as const

export const LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_COUNTS =
  Object.freeze({
    globalMessages: 631,
    globalGeneratorSchemaMessages: 214,
    globalHandlerSchemaMessages: 417,
    globalUnresolvedTopLevelSchemas: 0,
    globalRequestResponsePairs: 187,
    globalConstructorTypes: 533,
    currentJpPresentGlobalMessages: 470,
    identicalTopLevelSchemas: 367,
    changedTopLevelSchemas: 92,
    opcodeStableGlobalSchemaUnresolvedInJpComparison: 11,
    globalOnlyOrRemovedInCurrentJp: 161,
  } as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_EVIDENCE =
  Object.freeze({
    outgoing:
      'Original Global generator signatures prove client-to-server top-level argument order and C++ types.',
    incoming:
      'Original Global NetworkSession handler signatures prove server-to-client top-level argument order and C++ types.',
    nested:
      'Original Global constructor signatures provide nested C++ shape evidence but are not independently treated as proven serialization order.',
    jp:
      'Current JP may corroborate only when the shared message opcode and normalized schema satisfy the explicit lineage predicate.',
  } as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_STABLE_CRITICAL =
  Object.freeze([
    'C_GMCL_ACCOUNT_LOGIN_REQ_Response',
    'C_GMCL_CHAR_CREATE_REQ_Response',
    'C_GMCL_FIELD_SELECT_REQ',
    'C_GMCL_FIELD_INFO_REQ',
    'C_GMCL_FIELD_INFO_REQ_Response',
    'C_GMCL_ZONEIN_REQ',
    'C_GMCL_ZONEIN_REQ_Response',
    'S_GMCL_CHAR_MOVE_REQ',
    'C_GMCL_CHAR_TALK_REQ',
    'C_GMCL_CHAR_TALK_REQ_Response',
    'C_GMCL_BATTLE_ENTRY_REQ',
    'C_GMCL_BATTLE_ENTRY_REQ_Response',
    'S_GMCL_BATTLE_INITIALIZE',
    'C_GMCL_BATTLE_USE_SKILL_REQ_Response',
    'S_GMCL_BATTLE_BOUT_EVENT_DROP',
    'S_GMCL_ITEM_INFO',
    'S_GMCL_QUEST_INFO_STATE_RETURN',
  ] as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_CHANGED_CRITICAL =
  Object.freeze({
    accountLoginRequest: Object.freeze({
      name: 'C_GMCL_ACCOUNT_LOGIN_REQ',
      global:
        'string, string, int32, int32, uint32, string, string, string',
      currentJp: 'string, string, ClientLoginInfo',
    } as const),
    characterCreateRequest: Object.freeze({
      name: 'C_GMCL_CHAR_CREATE_REQ',
      global:
        'int32, string, int32, int32, int32, int32, int32, int32',
      currentJp:
        'uint32, int32, string, int32, int32, int32, int32, int32, int32',
    } as const),
    characterLoginResponse: Object.freeze({
      name: 'C_GMCL_CHAR_LOGIN_REQ_Response',
      global: 'e_GmClCharLoginReplyCode, t_CUID',
      currentJp: 'e_GmClCharLoginReplyCode, t_CUID, string',
    } as const),
    areaEnter: Object.freeze({
      name: 'S_GMCL_AREA_ENTER',
      globalFieldCount: 16,
      currentJpFieldCount: 19,
    } as const),
    characterMoveRequest: Object.freeze({
      name: 'C_GMCL_CHAR_MOVE_REQ',
      global:
        'float32, t_AreaUID, t_MapPos, t_MapPos, t_arrGridCoord',
      currentJp:
        'float32, t_AreaUID, t_MapPos, t_MapPos, t_arrGridCoord, t_WarpUID',
    } as const),
    npcAppear: Object.freeze({
      name: 'S_GMCL_NPC_APPEAR',
      globalFieldCount: 13,
      currentJpFieldCount: 16,
    } as const),
    enemyAppear: Object.freeze({
      name: 'S_GMCL_ENEMY_APPEAR',
      globalFieldCount: 17,
      currentJpFieldCount: 20,
    } as const),
    battleBoutInitialize: Object.freeze({
      name: 'S_GMCL_BATTLE_BOUT_INITIALIZE',
      globalFieldCount: 8,
      currentJpFieldCount: 11,
    } as const),
    battleUseSkillRequest: Object.freeze({
      name: 'C_GMCL_BATTLE_USE_SKILL_REQ',
      global:
        't_BattleRequestHeader, t_BoutCharUID, t_ItemUID, t_BattleSkillInfo, t_arrBoutCharUID, int32',
      currentJp:
        't_BattleRequestHeader, t_BoutCharUID, t_ItemUID, t_BattleSkillInfo, t_BoutCharUID, t_arrBoutCharUID, int32',
    } as const),
    battleResult: Object.freeze({
      name: 'S_GMCL_BATTLE_RESULT',
      global:
        't_BattleSystemUID, t_BattleResultInfo, uint32',
      currentJp:
        't_BattleSystemUID, t_BattleResultInfo, t_BattleResultPlayEffectInfo',
    } as const),
    questResult: Object.freeze({
      name: 'S_GMCL_QUEST_INFO_STATE_RESULT',
      globalFieldCount: 8,
      currentJpFieldCount: 9,
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_POLICY =
  Object.freeze({
    GLOBAL_DIRECT_GENERATOR_SIGNATURE:
      'Authoritative Global top-level client->server field order and types.',
    GLOBAL_DIRECT_NETWORKSESSION_HANDLER_SIGNATURE:
      'Authoritative Global top-level server->client field order and types.',
    GLOBAL_BINARY_DERIVED_CONSTRUCTOR_SHAPE:
      'Nested Global C++ shape only; not independently proven nested wire order.',
    GLOBAL_JP_IDENTICAL_TOP_LEVEL_SCHEMA:
      'JP corroborates an already recovered Global schema with same opcode and normalized top-level types.',
    JP_LINEAGE_OPCODE_STABLE_SCHEMA_CHANGED:
      'Opcode survived while schema changed; JP schema must not be backported.',
  } as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_SCHEMA_ARTIFACT =
  '/home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json' as const
