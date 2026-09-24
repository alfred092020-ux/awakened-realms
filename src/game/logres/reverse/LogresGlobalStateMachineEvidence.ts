export const LOGRES_GLOBAL_STATE_MACHINE_PROVENANCE =
  'CONFIRMED_GLOBAL_3_0_24_CRITICAL_STATE_MACHINE_WITH_EXPLICIT_SERVER_CEILINGS' as const

export const LOGRES_GLOBAL_STATE_MACHINE_COUNTS =
  Object.freeze({
    states: 23,
    transitions: 28,
    boundProtocolIds: 30,
  } as const)

export const LOGRES_GLOBAL_LOGIN_BRANCHES =
  Object.freeze({
    emptyCharacterList: Object.freeze({
      branchState: 1,
      destination: 'ReleaseScene_CharcterMake::create',
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478440',
    } as const),
    existingCharacterList: Object.freeze({
      branchState: 2,
      destination: 'ReleaseScene_CharacterLogin::create',
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478400',
    } as const),
    recovery: Object.freeze({
      branchState: 3,
      destination: null,
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f1b4_AND_0x0205f4a0',
      unresolved:
        'ReleaseScene_AccountLogIn::update has no direct scene factory for branch state 3.',
    } as const),
    titleFallback: Object.freeze({
      branchState: 4,
      destination: 'ReleaseScene_Title::create',
      evidence: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478450',
    } as const),
  } as const)

export const LOGRES_GLOBAL_CHARACTER_CREATE_TRANSITION =
  Object.freeze({
    successCode: 0,
    successDestination: 'ReleaseScene_CharacterLogin::create',
    evidence: 'GLOBAL_DIRECT_GHIDRA_0x02069078_PLUS_PLT_0x1478400',
  } as const)

export const LOGRES_GLOBAL_CHARACTER_LOGIN_CODES =
  Object.freeze({
    UNKNOWN: 0,
    SUCCESS: 1,
    FORWARD: 2,
    RECOVERY: 3,
    SPAWN: 4,
    ERR_LOGOUT_NOW: 5,
    ERR_CHANNEL_IS_FULL: 6,
    ERR_WORLD_IS_FULL: 7,
    acceptedCodes: Object.freeze([1, 2, 3, 4] as const),
    recoveryEmitsRecoveryEvent: true,
    code7HasDistinctErrorHandling: true,
  } as const)

export const LOGRES_GLOBAL_FIELD_TRANSITION_CHAIN =
  Object.freeze([
    'C_GMCL_FIELD_SELECT_REQ',
    'S_GMCL_FIELD_SELECT_REQ',
    'C_GMCL_FIELD_INFO_REQ',
    'C_GMCL_FIELD_INFO_REQ_Response',
    'C_GMCL_ZONEIN_REQ',
    'C_GMCL_ZONEIN_REQ_Response',
    'S_GMCL_AREA_ENTER',
  ] as const)

export const LOGRES_GLOBAL_AREA_ENTER_PROJECTION =
  Object.freeze({
    opcode: '0x6dff0f05',
    handler: 'NetworkSession::S_GMCL_AREA_ENTER',
    ghidraAddress: '0x01eb7590',
    action:
      'Construct AreaEnter NetworkObject and publish it through NetworkManager event dispatch.',
  } as const)

export const LOGRES_GLOBAL_ENCOUNTER_ENTRY =
  Object.freeze({
    requestOpcode: '0xfdff67d2',
    responseOpcode: '0x3228ac27',
    acceptedCode: 1,
    retryCode: 2,
    retrySeconds: 1.0,
    responseHandlerGhidraAddress: '0x01eba148',
  } as const)

export const LOGRES_GLOBAL_BATTLE_STATE_CHAIN =
  Object.freeze([
    'BATTLE_ENTRY_PENDING',
    'BATTLE_ACCEPTED',
    'BATTLE_INITIALIZING',
    'BOUT_ACTIVE',
    'BATTLE_RESULT',
    'REWARD_PROJECTION',
    'FIELD_RETURN',
  ] as const)

export const LOGRES_GLOBAL_BATTLE_HANDLER_EVIDENCE =
  Object.freeze({
    initialize: Object.freeze({
      opcode: '0xdb83b305',
      ghidraAddress: '0x01ebaec0',
    } as const),
    result: Object.freeze({
      opcode: '0x5b1ffeba',
      ghidraAddress: '0x01ebb04c',
    } as const),
    questResult: Object.freeze({
      opcode: '0x61a28538',
      ghidraAddress: '0x01ec21c4',
    } as const),
    questReturn: Object.freeze({
      opcode: '0xd5567b24',
      ghidraAddress: '0x01ec263c',
    } as const),
  } as const)

export const LOGRES_GLOBAL_STATE_MACHINE_GUARDRAILS =
  Object.freeze([
    'The client proves client transitions and server message projections, not retired-server validation or persistence decisions.',
    'Current-JP behavior is not authority where the recovered Global schema changed.',
    'Login recovery branch state 3 has no direct scene factory in the recovered AccountLogIn update path.',
    'Battle damage, stat, cooldown, EP, and reward-roll formulas are not invented.',
    'Exact post-battle field and warp payload values remain external retired-server evidence.',
  ] as const)

export const LOGRES_GLOBAL_STATE_MACHINE_ARTIFACT =
  Object.freeze({
    path: '/home/ubuntu/logres/artifacts/global-3024-state-machine-20260924.json',
    sha256:
      '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
  } as const)
