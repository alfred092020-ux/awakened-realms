export const LOGRES_GLOBAL_3024_BATTLE_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
  } as const)

export const LOGRES_GLOBAL_3024_BATTLE_SURFACE_COUNTS =
  Object.freeze({
    networkBattleMethods: 79,
    sequencerEventReceivers: 42,
    boutSystemMethods: 65,
    battleSystemMethods: 41,
    epManagerAndBeadMethods: 36,
  } as const)

export const LOGRES_GLOBAL_3024_BATTLE_COMPONENTS =
  Object.freeze([
    'BattleSystem',
    'BattleProtocolProcessor',
    'BoutSystem',
    'BoutSequencer',
    'BoutEPManager',
    'BoutEPBead',
  ] as const)

export const LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES =
  Object.freeze([
    'S_GMCL_BATTLE_INITIALIZE',
    'S_GMCL_BATTLE_BOUT_INITIALIZE',
    'S_GMCL_BATTLE_SEQUENCER_INITIALIZE',
    'S_GMCL_BATTLE_BOUTCHAR_APPEAR',
    'S_GMCL_BATTLE_ITEM_SKILL_LIST',
    'S_GMCL_BATTLE_ESCAPE_SKILL',
    'S_GMCL_BATTLE_STAY_TIME',
    'S_GMCL_BATTLE_RESULT',
  ] as const)

export const LOGRES_GLOBAL_3024_BATTLE_CLIENT_RESPONSE_SURFACE =
  Object.freeze([
    'C_GMCL_BATTLE_ENTRY_REQ_Response',
    'C_GMCL_BATTLE_USE_SKILL_REQ_Response',
    'C_GMCL_BATTLE_USE_GIVE_UP_REQ_Response',
    'C_GMCL_BATTLE_STALEMATE_REQ_Response',
    'C_GMCL_BATTLE_USE_CONTINUE_SKILL_REQ_Response',
    'C_GMCL_BATTLE_USE_REACTION_SKILL_REQ_Response',
    'C_GMCL_BATTLE_CHANGE_USE_SKILL_MODE_REQ_Response',
  ] as const)

export const LOGRES_GLOBAL_3024_BATTLE_EVENT_FAMILIES =
  Object.freeze({
    sequencing: Object.freeze([
      'SEQUENCE_BEGIN',
      'SEQUENCE_END',
      'BOUT_STANDBY_TIME',
      'BOUT_START_COUNTDOWN',
    ] as const),
    skills: Object.freeze([
      'CHARGE_SKILL',
      'CANCEL_CHARGE',
      'FAILED_CHARGE',
      'EXECUTE_SKILL',
      'WAIT_SKILL',
      'RECAST_SKILL',
      'RESET_RECAST_SKILL',
      'SEAL_SKILL',
      'SELECT_REACTION_SKILL',
      'EXECUTE_REACTION_SKILL',
    ] as const),
    targeting: Object.freeze([
      'CHAR_TARGET_LOCK',
      'CHAR_TARGET_UNLOCK',
    ] as const),
    statusAndEffects: Object.freeze([
      'STATUS_CHANGED',
      'ADD_ENCHANT',
      'REMOVE_ENCHANT',
      'EFFECT_GENERATED',
      'PLAY_LOOP_EFFECT',
      'STOP_LOOP_EFFECT',
      'ADD_SKILL_STATUS_EFFECT',
      'REMOVE_SKILL_STATUS_EFFECT',
      'PLAY_SKILL_STATUS_EFFECT',
      'CHAR_SHAPE_CHANGE',
      'PLAY_BATTLEPRODUCTION_EVENT',
    ] as const),
    lifeAndRewards: Object.freeze([
      'DEAD',
      'REVIVE',
      'DROP',
      'UPDATE_REMAINLIFE_INFO',
      'BOUT_RESULT',
      'BOUT_FINISH',
    ] as const),
    gauges: Object.freeze([
      'GENERATE_GAUGE',
      'UPDATE_GAUGE',
      'DELETE_GAUGE',
    ] as const),
    continuation: Object.freeze([
      'START_CONTINUE',
      'END_CONTINUE',
      'START_CONTINUE_COUNTDOWN',
      'END_CONTINUE_COUNTDOWN',
      'START_GIVE_UP',
      'END_GIVE_UP',
      'START_STALEMATE',
      'STAY_TIME_PENALTY',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE =
  Object.freeze({
    topLevelLifecycle:
      'BattleSystem',
    activeBoutLifecycle:
      'BoutSystem',
    protocolProjection:
      'BattleProtocolProcessor',
    eventOrdering:
      'BoutSequencer',
    epProjection:
      'BoutEPManager',
    resultPresentation:
      'BattleSystem.displayResult',
    finishTransition:
      'BoutSystem.goToFinishFlow',
    authorityModel:
      'server-authored-sequenced-events',
    rewardModel:
      'server-payload-driven-drop-and-result-events',
  } as const)

export const LOGRES_GLOBAL_3024_BATTLE_UNRESOLVED =
  Object.freeze([
    'server-side damage formulas',
    'server-side enemy stat formulas',
    'exact cooldown and recast values',
    'exact EP arithmetic and caps for every skill',
    'exact reward quantities and roll tables',
    'exact historical tutorial opponent stats',
  ] as const)
