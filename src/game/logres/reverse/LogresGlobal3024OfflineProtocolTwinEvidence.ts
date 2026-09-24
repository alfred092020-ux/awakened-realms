export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_PROVENANCE =
  'CONFIRMED_GLOBAL_3_0_24_OFFLINE_PROTOCOL_TWIN' as const

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_POLICY =
  Object.freeze({
    networkAccess: 'NO_SOCKET_OR_REMOTE_SERVER_ACCESS',
    serverAuthority:
      'Server validation/state values are explicit deterministic offline stubs; they are not inferred from current JP.',
    exactBytes:
      'Exact fixture bytes are emitted only when every top-level field has directly supported Global serialization.',
    schemaOnly:
      'Messages with unresolved nested/composite serializers remain deterministic schema fixtures without fabricated wire bytes.',
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE =
  Object.freeze({
    gmclFunctionId: 'uint32 little-endian first field',
    contractId: 0x31318435,
    splitToContract:
      'uint32_le contractId + uint32_le nestedBufferLength + nestedBufferBytes',
    compressorThreshold: 0x401,
    compressorRaw: '0x00 + raw bytes',
    compressorCompressed: '0x01 + Snappy RawCompress bytes',
    packetize:
      '0x01 + uint32_le sequence + base128_varuint payloadLength + payload',
    packetMarker: 0x01,
    encryptionCheckpoint: false,
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES =
  Object.freeze({
    totalMessages: 631,
    exactTopLevelWireFixtures: 225,
    schemaOnlyOrPartialFixtures: 406,
    criticalReplayEvents: 30,
    criticalExactClientFrames: 10,
    criticalServerAuthorityStubs: 20,
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_DIRECT_SERIALIZERS =
  Object.freeze({
    primitives: Object.freeze([
      'int32',
      'uint32',
      'float32',
      'bool8',
      'string=u32 byte length + UTF-8 bytes',
    ] as const),
    coreStructs: Object.freeze([
      'ObjectUID',
      't_AreaUID',
      't_BattleRequestHeader',
      't_BattleSkillInfo',
      't_BattleSystemUID',
      't_BoutCharUID',
      't_BoutSystemUID',
      't_CUID',
      't_FieldUID',
      't_GridCoord',
      't_ItemUID',
      't_MapPos',
      't_QuestUID',
      't_SkillUID',
      't_SymbolUID',
      't_WarpUID',
    ] as const),
    directArrays: Object.freeze({
      t_arrBoutCharUID: 'uint32 count + repeated t_BoutCharUID',
      t_arrGridCoord: 'uint32 count + repeated t_GridCoord',
    } as const),
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_DRIFT_GUARDS =
  Object.freeze({
    characterMove:
      'Global C_GMCL_CHAR_MOVE_REQ = float32, t_AreaUID, t_MapPos, t_MapPos, t_arrGridCoord; no trailing t_WarpUID.',
    battleUseSkill:
      'Global C_GMCL_BATTLE_USE_SKILL_REQ = t_BattleRequestHeader, t_BoutCharUID, t_ItemUID, t_BattleSkillInfo, t_arrBoutCharUID, int32; no extra single target field before the array.',
    characterCreate:
      'Global C_GMCL_CHAR_CREATE_REQ remains the recovered eight-field Global form, not the nine-field current-JP schema.',
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_SELF_TESTS =
  Object.freeze({
    rawRoundTrip: true,
    snappyRoundTrip: true,
    rawFrameSha256:
      'ec3da12b7a393550dcc3718879d119cbc41992fb1974712ce58b2cbdd8ddc4d0',
    compressedFrameSha256:
      '70ab9719ce2678b721d3e29589af369dc8155a5a2fc581dd00e670ea657704cd',
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_ARTIFACT =
  Object.freeze({
    path:
      '/home/ubuntu/logres/artifacts/global3024-offline-protocol-twin-20260924.json',
    sha256:
      '52a0b140d95e904d57f48e1c936c1efc81c34e0c32a70fbd958b967a4c991a5c',
  } as const)

export const LOGRES_GLOBAL_3024_OFFLINE_TWIN_CEILINGS =
  Object.freeze([
    'Unknown nested/composite serializers stay schema-only until direct Global Buffer push/pop evidence is indexed.',
    'Retired server validation, persistence, matchmaking, economy decisions and dynamic values are represented only by explicit offline authority stubs.',
    'Offline replay proves recovered client wire/framing behavior; it does not recreate retired production server state.',
  ] as const)
