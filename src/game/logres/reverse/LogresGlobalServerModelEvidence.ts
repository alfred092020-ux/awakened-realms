export const LOGRES_GLOBAL_SERVER_MODEL_PROVENANCE =
  'CONFIRMED_GLOBAL_3_0_24_CLIENT_OBSERVED_SERVER_BOUNDARY_MODEL' as const

export const LOGRES_GLOBAL_SERVER_MODEL_SOURCE =
  Object.freeze({
    protocolSchemaPath:
      '/home/ubuntu/logres/artifacts/global-jp-protocol-schema-20260924.json',
    protocolSchemaSha256:
      '9e9583da01db8aa4a7c808397cbf740114469902862bc5984631bbb6815a1f16',
    modelArtifactPath:
      '/home/ubuntu/logres/artifacts/global3024-client-observed-server-model-20260924.json',
    modelArtifactSha256:
      '8d21821cbd07de50d34d06ee547ec71dd3ae3f8df27c2a5a5187d165d1e3e369',
  } as const)

export const LOGRES_GLOBAL_SERVER_MODEL_SEMANTICS =
  'Normalized client-observed projections and correlations derived from original Global protocol/type evidence. These are not claims about database tables, server classes, persistence topology, or validation implementation.' as const

const projection = (
  id: string,
  domain: string,
  identityOrCorrelationTypes: readonly string[],
  recordShapes: Readonly<Record<string, number>>,
  evidenceMessages: readonly string[],
) =>
  Object.freeze({
    id,
    domain,
    classification: 'GLOBAL_CLIENT_OBSERVED_PROJECTION' as const,
    identityOrCorrelationTypes: Object.freeze(identityOrCorrelationTypes),
    recordShapes: Object.freeze(recordShapes),
    evidenceMessages: Object.freeze(evidenceMessages),
  })

export const LOGRES_GLOBAL_SERVER_MODEL_ENTITIES =
  Object.freeze({
    account: projection(
      'AccountProjection',
      'account',
      ['t_AccountUID'],
      {
        t_AccountCharInfo: 4,
        t_AccountCharInfoList: 1,
        CharacterListDataOne: 5,
      },
      [
        'S_GMCL_ACCOUNT_CHAR_INFO',
        'S_GMCL_CHAR_LIST',
        'C_GMCL_ACCOUNT_LOGIN_REQ_Response',
      ],
    ),
    character: projection(
      'CharacterProjection',
      'character',
      ['t_CUID'],
      {
        CharacterListDataOne: 5,
        t_ObjectParamOne: 14,
        t_PlayerFieldNameInfo: 1,
      },
      [
        'C_GMCL_CHAR_CREATE_REQ_Response',
        'S_GMCL_OBJECT_PARAM',
        'S_GMCL_CHAR_SHAPE',
        'S_GMCL_CHAR_PROFILE',
        'S_GMCL_CHAR_SETUP_FINISH',
      ],
    ),
    field: projection(
      'FieldPresenceProjection',
      'field',
      ['ObjectUID', 't_FieldUID', 't_AreaUID'],
      {
        MapChannelInfo: 5,
        t_CharLocation: 2,
      },
      [
        'C_GMCL_FIELD_SELECT_REQ',
        'C_GMCL_FIELD_INFO_REQ_Response',
        'C_GMCL_ZONEIN_REQ_Response',
        'S_GMCL_AREA_ENTER',
        'S_GMCL_PLAYER_APPEAR',
        'S_GMCL_NPC_APPEAR',
        'S_GMCL_ENEMY_APPEAR',
        'C_GMCL_CHAR_MOVE_REQ',
        'S_GMCL_CHAR_MOVE_REQ',
      ],
    ),
    battle: projection(
      'BattleSessionProjection',
      'battle',
      ['t_BattleSystemUID', 't_BoutSystemUID', 't_BoutCharUID'],
      {
        t_BoutEventHeader: 4,
        t_BattleResultInfo: 2,
        t_BattleDropResultInfo: 2,
        t_BattleUseSkillResponseInfo: 6,
      },
      [
        'C_GMCL_BATTLE_ENTRY_REQ',
        'C_GMCL_BATTLE_ENTRY_REQ_Response',
        'S_GMCL_BATTLE_INITIALIZE',
        'S_GMCL_BATTLE_BOUT_INITIALIZE',
        'S_GMCL_BATTLE_BOUT_EVENT_EXECUTE_SKILL',
        'S_GMCL_BATTLE_BOUT_EVENT_DROP',
        'S_GMCL_BATTLE_RESULT',
      ],
    ),
    inventory: projection(
      'InventoryProjection',
      'inventory',
      ['t_CUID', 't_ItemUID'],
      {
        t_ItemInfoOne: 65,
        t_ItemDetail: 20,
      },
      [
        'S_GMCL_ITEM_INFO',
        'S_GMCL_ITEM_DETAIL',
        'C_GMCL_ITEM_MOVE_REQ',
        'C_GMCL_MOVE_TO_GARAGE',
        'C_GMCL_MOVE_FROM_GARAGE_Response',
      ],
    ),
    quest: projection(
      'QuestProgressProjection',
      'quest',
      ['t_QuestUID', 't_QuestIssueUID'],
      {
        t_QuestReward: 1,
        t_QuestAcceptRequestParam: 12,
      },
      [
        'S_GMCL_QUEST_INFO_BASE',
        'S_GMCL_QUEST_INFO_STATE_PROGRESS_START',
        'S_GMCL_QUEST_INFO_STATE_PROGRESS_UPDATE',
        'S_GMCL_QUEST_INFO_STATE_RESULT',
        'S_GMCL_QUEST_INFO_STATE_RETURN',
        'C_GMCL_QUEST_ACCEPT_REQ',
        'C_GMCL_QUEST_RETIRE_REQ',
      ],
    ),
    partySocial: projection(
      'PartySocialProjection',
      'party_social',
      ['t_GmPartyUID', 't_CUID', 'clan_uid_t', 'destination_t'],
      {
        t_GmPartySyncInfo: 5,
        destination_t: 4,
        t_ClanConfig: 5,
      },
      [
        'S_GMCL_PARTY_SYNC_PARTYINFO',
        'C_GMCL_PARTY_LEAVE_REQ_Response',
        'C_GMCL_FRIEND_ADD_REQ',
        'S_GMCL_CHAT',
        'C_GMCL_CHAT_SEND_REQ',
        'S_GMCL_CLAN_SYNC_CLANINFO',
      ],
    ),
    economy: projection(
      'EconomyProjection',
      'economy',
      ['t_CUID'],
      {
        t_Ticket: 2,
        t_GmShopItemInfo: 14,
      },
      [
        'S_GMCL_PAYMENT_POINT',
        'S_GMCL_NOTIFY_ALT_MONEY',
        'S_GMCL_SHOP_ITEM_LIST',
        'C_GMCL_GACHA_BUY_REQ',
        'S_GMCL_GACHA2_LOT_RESULT',
        'C_GMCL_TICKET_LIST_REQ_Response',
      ],
    ),
    reward: projection(
      'RewardProjection',
      'reward',
      ['t_CUID', 't_QuestUID', 't_BattleSystemUID'],
      {
        t_QuestReward: 1,
        t_BattleResultInfo: 2,
        t_BattleDropResultInfo: 2,
      },
      [
        'S_GMCL_BATTLE_BOUT_EVENT_DROP',
        'S_GMCL_BATTLE_RESULT',
        'S_GMCL_QUEST_INFO_STATE_RESULT',
        'S_GMCL_QUEST_INFO_STATE_STAMP_REWARD',
        'S_GMCL_LOGINBONUS_NOTIFICATION',
      ],
    ),
  } as const)

const relation = (
  source: string,
  kind: string,
  target: string,
  evidenceMessages: readonly string[],
) =>
  Object.freeze({
    source,
    relation: kind,
    target,
    classification: 'CLIENT_OBSERVED_RELATION' as const,
    evidenceMessages: Object.freeze(evidenceMessages),
  })

export const LOGRES_GLOBAL_SERVER_MODEL_RELATIONSHIPS =
  Object.freeze([
    relation(
      'AccountProjection',
      'HAS_CHARACTER_PROJECTION',
      'CharacterProjection',
      ['S_GMCL_ACCOUNT_CHAR_INFO', 'S_GMCL_CHAR_LIST'],
    ),
    relation(
      'CharacterProjection',
      'HAS_FIELD_PRESENCE',
      'FieldPresenceProjection',
      ['S_GMCL_PLAYER_APPEAR', 'C_GMCL_CHAR_MOVE_REQ'],
    ),
    relation(
      'CharacterProjection',
      'HAS_INVENTORY_PROJECTION',
      'InventoryProjection',
      ['S_GMCL_ITEM_INFO', 'S_GMCL_ITEM_DETAIL'],
    ),
    relation(
      'CharacterProjection',
      'HAS_QUEST_PROGRESS',
      'QuestProgressProjection',
      ['S_GMCL_QUEST_INFO_BASE', 'S_GMCL_QUEST_INFO_STATE_PROGRESS_START'],
    ),
    relation(
      'CharacterProjection',
      'PARTICIPATES_IN',
      'BattleSessionProjection',
      ['C_GMCL_BATTLE_ENTRY_REQ', 'S_GMCL_BATTLE_BOUTCHAR_APPEAR'],
    ),
    relation(
      'CharacterProjection',
      'PARTICIPATES_IN',
      'PartySocialProjection',
      ['S_GMCL_PARTY_SYNC_PARTYINFO', 'C_GMCL_FRIEND_ADD_REQ'],
    ),
    relation(
      'CharacterProjection',
      'HAS_ECONOMY_PROJECTION',
      'EconomyProjection',
      ['S_GMCL_PAYMENT_POINT', 'S_GMCL_NOTIFY_ALT_MONEY'],
    ),
    relation(
      'BattleSessionProjection',
      'EMITS_REWARD_PROJECTION',
      'RewardProjection',
      ['S_GMCL_BATTLE_BOUT_EVENT_DROP', 'S_GMCL_BATTLE_RESULT'],
    ),
    relation(
      'QuestProgressProjection',
      'EMITS_REWARD_PROJECTION',
      'RewardProjection',
      [
        'S_GMCL_QUEST_INFO_STATE_RESULT',
        'S_GMCL_QUEST_INFO_STATE_STAMP_REWARD',
      ],
    ),
    relation(
      'RewardProjection',
      'MAY_UPDATE',
      'InventoryProjection',
      ['S_GMCL_BATTLE_BOUT_EVENT_DROP', 'S_GMCL_ITEM_INFO'],
    ),
  ] as const)

export const LOGRES_GLOBAL_SERVER_MODEL_CONSTRUCTOR_GUARDRAIL =
  'Constructor positional shapes are Global binary-derived client structure evidence. They are not independently proven database rows, persistence schemas, or nested wire order.' as const

export const LOGRES_GLOBAL_SERVER_MODEL_JP_POLICY =
  'Current JP may corroborate only message/type semantics already recovered from Global when explicit schema lineage is stable; JP does not define the historical Global server model.' as const

export const LOGRES_GLOBAL_SERVER_MODEL_EXTERNAL_CEILINGS =
  Object.freeze([
    'Server validation rules and rejection logic beyond observable result messages.',
    'Persistence/database schema, transaction boundaries, locking and commit order.',
    'Authoritative economy formulas, anti-cheat and abuse detection.',
    'Matchmaking internals, hidden timers and dynamic event configuration not sent to the client.',
    'Reward grant atomicity/idempotency beyond client-observed result/update messages.',
  ] as const)
