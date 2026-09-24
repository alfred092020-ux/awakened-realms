export const LOGRES_GLOBAL_3024_PROTOCOL_SOURCE = Object.freeze({
  clientVersion: '3.0.24',
  libgameArm64Sha256: 'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
  protocolCatalogSha256: '13e9a20c9c97e16a9cd84a9a0871e282c7f9ef7df4cbbc105e051985b6543ffe',
  constructorCatalogSha256: '8921bce382b121715adedd52668c72af5adbb0027f0559eaca3dbc8d85e517f0',
  provenance: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_NATIVE_PROTOCOL',
} as const)

export const LOGRES_GLOBAL_3024_PROTOCOL_SURFACE = Object.freeze({
  functionIds: 631,
  clientMessages: 205,
  serverMessages: 239,
  responseMessages: 187,
  generatorSignatures: 214,
  constructorTypes: 533,
} as const)

export const LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE = Object.freeze({
  payloadBuffer: 'oneup::Buffer',
  functionIdBytes: 4,
  functionIdPosition: 'first-field',
  functionIdByteOrder: 'little-endian-on-original-AArch64-client',
  generatorEvidence: Object.freeze([
    'ACCOUNT_LOGIN writes 0x740a055c before payload fields',
    'CHAR_MOVE writes 0x7d8ff367 before payload fields',
  ] as const),
  sender: 'ClientGmClProtoSender<ClientGmClProtoProcedureBinaryGenerator>::send',
  senderProperties: Object.freeze({
    ContractId: '0x31318435',
    Encryption: 'bool',
  } as const),
  senderBehavior: Object.freeze([
    'construct TransactionData from generated Buffer',
    'set ContractId property to 0x31318435',
    'set Encryption property from sender boolean',
    'call oneup::Connection::sendData',
  ] as const),
  packetizeFrame: Object.freeze({
    marker: '0x01',
    sequence: 'uint32 little-endian incrementing counter',
    payloadLength: 'base-128 varuint, 7 data bits per byte, high-bit continuation',
    payload: 'TransactionData bytes containing GmCl FUNCTION_ID + typed payload',
    reverseParser: 'confirmed by Packetize::transferBackward',
  } as const),
  socketTransportBeyondPacketize: 'UNRESOLVED',
} as const)

export const LOGRES_GLOBAL_3024_CORE_TYPES = Object.freeze({
  t_CUID: 'int, int',
  t_AreaUID: 'int, int',
  t_MapPos: 'float, float',
  t_GridCoord: 'int, int',
  t_FieldUID: 'int, int',
  t_WarpUID: 'int, int',
  t_SymbolUID: 'int, int',
  t_QuestUID: 'int, int',
  t_BoutCharUID: 'int, int',
  t_ItemUID: 'int, int',
  t_ReauthCode: 'int, int',
  t_BattleRequestHeader: 't_BattleSystemUID, t_BoutSystemUID',
  t_BattleSkillInfo: 't_SkillUID, unsigned int, unsigned int',
  destination_t: 'unsigned int, channel_t, topic_t, auxiliary_t',
} as const)

export const LOGRES_GLOBAL_3024_ACCOUNT_LOGIN_RESULTS = Object.freeze({
  UNKNOWN: 0, SUCCESS: 1, REAUTH_SUCCESS: 2, NOT_AGREEMENT: 3,
  DISALLOW: 4, INVALID_SESSION_TOKEN: 5, CLIENT_VERSION_ERROR: 6, SUSPENDED: 7,
} as const)

export const LOGRES_GLOBAL_3024_CHAR_CREATE_RESULTS = Object.freeze({
  SUCCESS: 0, DUPLICATION: 1, WORD_FILTER: 2, OTHER_ERR: 3,
} as const)

export const LOGRES_GLOBAL_3024_CHAR_LOGIN_RESULTS = Object.freeze({
  UNKNOWN: 0, SUCCESS: 1, FORWARD: 2, RECOVERY: 3, SPAWN: 4,
  ERR_LOGOUT_NOW: 5, ERR_CHANNEL_IS_FULL: 6, ERR_WORLD_IS_FULL: 7,
} as const)

const request = (name: string, functionId: number, hex: string, schema?: string) =>
  Object.freeze({ name, functionId, hex, ...(schema ? { schema } : {}) })

const exchange = (
  requestMessage: ReturnType<typeof request>,
  responseMessage?: ReturnType<typeof request>,
) => Object.freeze({
  request: requestMessage,
  ...(responseMessage ? { response: responseMessage } : {}),
})

export const LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES = Object.freeze({
  accountLogin: exchange(
    request('C_GMCL_ACCOUNT_LOGIN_REQ', 1946813788, '0x740a055c', 'string, string, int, int, uint, string, string, string'),
    request('C_GMCL_ACCOUNT_LOGIN_REQ_Response', 25722962, '0x01888052'),
  ),
  accountReauth: exchange(request('C_GMCL_ACCOUNT_REAUTH_REQ', 3552546271, '0xd3bf8ddf', 'string, t_ReauthCode')),
  characterLogin: exchange(
    request('C_GMCL_CHAR_LOGIN_REQ', 620278506, '0x24f8b2ea', 't_CUID'),
    request('C_GMCL_CHAR_LOGIN_REQ_Response', 430622204, '0x19aac5fc'),
  ),
  characterCreate: exchange(
    request('C_GMCL_CHAR_CREATE_REQ', 510385705, '0x1e6bde29', 'int, string, int, int, int, int, int, int'),
    request('C_GMCL_CHAR_CREATE_REQ_Response', 1684342767, '0x646507ef'),
  ),
  fieldSelect: exchange(request('C_GMCL_FIELD_SELECT_REQ', 268550344, '0x1001c0c8', 't_FieldUID, int, int')),
  fieldInfo: exchange(
    request('C_GMCL_FIELD_INFO_REQ', 1468596778, '0x5789022a', 'int'),
    request('C_GMCL_FIELD_INFO_REQ_Response', 2956113123, '0xb032b4e3'),
  ),
  zoneIn: exchange(
    request('C_GMCL_ZONEIN_REQ', 2251603041, '0x8634bc61', 't_WarpUID'),
    request('C_GMCL_ZONEIN_REQ_Response', 3075017798, '0xb7490c46'),
  ),
  characterMove: exchange(request('C_GMCL_CHAR_MOVE_REQ', 2106585959, '0x7d8ff367', 'float, t_AreaUID, t_MapPos, t_MapPos, t_arrGridCoord')),
  characterTalk: exchange(
    request('C_GMCL_CHAR_TALK_REQ', 1396260262, '0x53393da6', 't_CUID'),
    request('C_GMCL_CHAR_TALK_REQ_Response', 3613002719, '0xd75a0bdf'),
  ),
  battleEntry: exchange(
    request('C_GMCL_BATTLE_ENTRY_REQ', 4261373906, '0xfdff67d2', 't_AreaUID, t_MapPos, int, t_SymbolUID, uint'),
    request('C_GMCL_BATTLE_ENTRY_REQ_Response', 841526311, '0x3228ac27'),
  ),
  battleUseSkill: exchange(
    request('C_GMCL_BATTLE_USE_SKILL_REQ', 3604126339, '0xd6d29a83', 't_BattleRequestHeader, t_BoutCharUID, t_ItemUID, t_BattleSkillInfo, t_arrBoutCharUID, int'),
    request('C_GMCL_BATTLE_USE_SKILL_REQ_Response', 4033762592, '0xf06e5520'),
  ),
  questReady: exchange(request('C_GMCL_QUEST_READY', 449551060, '0x1acb9ad4', 't_QuestUID')),
  questNextState: exchange(request('C_GMCL_QUEST_NEXT_STATE_REQ', 287101980, '0x111cd41c', 't_QuestUID, int, bool')),
  chatSend: exchange(
    request('C_GMCL_CHAT_SEND_REQ', 1865766449, '0x6f355631', 'destination_t, string'),
    request('C_GMCL_CHAT_SEND_REQ_Response', 1077359975, '0x40373567'),
  ),
  gachaBuy: exchange(request('C_GMCL_GACHA_BUY_REQ', 1353764312, '0x50b0cdd8', 'int, int')),
  communicationPing: exchange(
    request('S_COMMUNICATION_PING_REQ', 175691553, '0x0a78d721'),
    request('S_COMMUNICATION_PING_REQ_Response', 243496962, '0x0e837802', 'int, int, int, int'),
  ),
} as const)

export const LOGRES_GLOBAL_3024_SERVER_PUSHES = Object.freeze({
  npcAppear: request('S_GMCL_NPC_APPEAR', 455001580, '0x1b1ec5ec'),
  enemyAppear: request('S_GMCL_ENEMY_APPEAR', 4268853861, '0xfe718a65'),
  activeEnemyState: request('S_GMCL_NOTIFY_ACTIVE_ENEMY_STATE', 3496200715, '0xd063ca0b'),
  battleResult: request('S_GMCL_BATTLE_RESULT', 1528823482, '0x5b1ffeba'),
  battleDrop: request('S_GMCL_BATTLE_BOUT_EVENT_DROP', 1250495900, '0x4a890d9c'),
  itemInfo: request('S_GMCL_ITEM_INFO', 4110668784, '0xf503d3f0'),
  questProgressStart: request('S_GMCL_QUEST_INFO_STATE_PROGRESS_START', 3601809362, '0xd6af3fd2'),
  questProgressUpdate: request('S_GMCL_QUEST_INFO_STATE_PROGRESS_UPDATE', 3067670163, '0xb6d8ee93'),
  questResult: request('S_GMCL_QUEST_INFO_STATE_RESULT', 1638040888, '0x61a28538'),
} as const)

export const LOGRES_GLOBAL_3024_PROTOCOL_UNRESOLVED = Object.freeze([
  'transport bytes below the confirmed oneup Packetize layer, if any',
  'transport encryption/compression policy for every connection/message class',
  'semantic field names for primitive parameters whose native signatures expose only C++ types',
  'server-side validation and persistence behavior not present in the client binary',
  'historical production server addresses and HostEntry values',
] as const)
