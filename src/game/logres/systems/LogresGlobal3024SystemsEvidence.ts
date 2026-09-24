export const LOGRES_GLOBAL_3024_SYSTEMS_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_NATIVE_PROTOCOL_AND_BUNDLED_CONFIG',
    numericFunctionIdCount:
      631,
    numericEnumConstantCount:
      507,
  } as const)

export const LOGRES_GLOBAL_3024_SYSTEMS_SURFACE_COUNTS =
  Object.freeze({
    overlappingKeywordSurface:
      true,
    itemEquipment:
      Object.freeze({
        networkSignatures: 99,
        nativeClasses: 570,
        nativeMethods: 4412,
      } as const),
    questMission:
      Object.freeze({
        networkSignatures: 43,
        nativeClasses: 256,
        nativeMethods: 2149,
      } as const),
    jobSkillProgression:
      Object.freeze({
        networkSignatures: 51,
        nativeClasses: 215,
        nativeMethods: 1338,
      } as const),
    shopGachaEconomy:
      Object.freeze({
        networkSignatures: 32,
        nativeClasses: 111,
        nativeMethods: 958,
      } as const),
    partyFriendMercenary:
      Object.freeze({
        networkSignatures: 13,
        nativeClasses: 51,
        nativeMethods: 338,
      } as const),
    clanCommunity:
      Object.freeze({
        networkSignatures: 26,
        nativeClasses: 108,
        nativeMethods: 862,
      } as const),
    chatMailSocial:
      Object.freeze({
        networkSignatures: 43,
        nativeClasses: 168,
        nativeMethods: 1417,
      } as const),
  } as const)

export const LOGRES_GLOBAL_3024_ITEM_RESULTS =
  Object.freeze({
    OK: 0,
    BAD_REQUEST: 1,
    FORBIDDEN: 2,
    NOT_FOUND: 3,
    INTERNAL_SERVER_ERROR: 4,
    SERVICE_UNAVAILABLE: 5,
    NOT_READY: 6,
    CONFLICT: 7,
    NO_SPACE_LEFT: 8,
    NO_CHANGES: 9,
    CANCELED: 10,
    PAYMENT_REQUIRED: 11,
    OUT_OF_DATE: 12,
    NOT_IMPLEMENTED: 13,
  } as const)

export const LOGRES_GLOBAL_3024_FUSION_RESULTS =
  Object.freeze({
    OK: 0,
    BAD_REQUEST: 1,
    FORBIDDEN: 2,
    INTERNAL_SERVER_ERROR: 3,
    GONE: 4,
    NOT_SUPPORTED: 5,
  } as const)

export const LOGRES_GLOBAL_3024_DAILY_MISSION_RESULTS =
  Object.freeze({
    UNKNOWN: 0,
    SUCCESS: 1,
    NOT_FOUND: 2,
    CAN_NOT_COMPLETE: 3,
    ALREADY_FINISHED: 4,
    EXPIRED: 5,
  } as const)

export const LOGRES_GLOBAL_3024_CHAT_RESULTS =
  Object.freeze({
    OK: 0,
    BAD_REQUEST: 1,
    FORBIDDEN: 2,
    NOT_FOUND: 3,
    INTERNAL_SERVER_ERROR: 4,
    PAYMENT_REQUIRED: 5,
    NOT_IMPLEMENTED: 6,
    NOT_READY: 7,
    SERVICE_UNAVAILABLE: 8,
    CONFLICT: 9,
    NO_CHANGES: 10,
    NO_SPACE_LEFT: 11,
    CANCELED: 12,
    NAME_IS_IN_USE: 13,
    NOT_A_MEMBER: 14,
    WRITE_ONCE: 15,
    BAD_NAME: 16,
    TOO_LONG_DESCRIPTION: 17,
    OUT_OF_DATE: 18,
    TOO_LONG_NAME: 19,
  } as const)

export const LOGRES_GLOBAL_3024_ITEMS =
  Object.freeze({
    networkClient:
      'item::NetworkClient',
    keyClasses:
      Object.freeze([
        'SelectEquipment',
        'EquipmentDetailWindow',
        'ItemSelectorView',
        'ItemListWindow',
        'ChangeEquipment',
        'EquipmentBoardList',
        'FavoriteEquipments',
        'garage::GarageManager',
      ] as const),
    requests:
      Object.freeze({
        itemMove:
          Object.freeze({
            name: 'C_GMCL_ITEM_MOVE_REQ',
            functionId: 683580635,
            generator:
              'generate_C_GMCL_ITEM_MOVE_REQ(Buffer&, int, t_arrItemMoveParam const&)',
            moveParamCtor:
              't_ItemMoveParam(t_ItemUID, int, t_ItemUID, int)',
          } as const),
        itemUse:
          Object.freeze({
            name: 'C_GMCL_ITEM_USE_REQ',
            functionId: 2618211351,
          } as const),
        buy:
          Object.freeze({
            name: 'C_GMCL_BUY_ITEM_REQ',
            functionId: 1793742103,
            generator:
              'generate_C_GMCL_BUY_ITEM_REQ(Buffer&, t_ScriptUID const&, t_GmBuyItemInfoArray const&)',
          } as const),
        sell:
          Object.freeze({
            name: 'C_GMCL_SELL_ITEM_REQ',
            functionId: 4050998581,
            contract:
              'C_GMCL_SELL_ITEM_REQ(t_ScriptUID, t_GmSellItemInfoArray)',
          } as const),
        fusion:
          Object.freeze({
            name: 'C_GMCL_FUSION',
            functionId: 4019073091,
            contract:
              'C_GMCL_FUSION(uint, fusion_type, fusion_direction, item_list, item_list, alt_money_list, uint, uint, fusion_estimation_list)',
          } as const),
        evolutionGraph:
          Object.freeze({
            name:
              'C_GMCL_GET_EVOLUTION_GRAPH',
            functionId:
              3811861866,
            contract:
              'C_GMCL_GET_EVOLUTION_GRAPH(uint, uint)',
          } as const),
      } as const),
    serverProjection:
      Object.freeze({
        itemInfo:
          Object.freeze({
            name: 'S_GMCL_ITEM_INFO',
            functionId: 4110668784,
          } as const),
        itemBoxInfo:
          Object.freeze({
            name: 'S_GMCL_ITEM_BOX_INFO',
            functionId: 2960062454,
          } as const),
        dividedItemInfo:
          'S_GMCL_ITEM_INFO_DEVIDE_SEND_PARAM',
        endOfItems:
          'S_GMCL_END_OF_ITEMS',
        garageModified:
          'S_GMCL_NOTIFY_GARAGE_MODIFIED',
        garageModifiedWithDetail:
          'S_GMCL_NOTIFY_GARAGE_MODIFIED_WITH_DETAIL',
      } as const),
    networkClientReceivers:
      Object.freeze([
        'receiveItemInfo',
        'receiveItemBoxInfo',
        'receiveDevideSendInfo',
        'receiveItemBoxCapacity',
        'receiveNotifyEndOfItems',
        'receiveLoadWeaponOrder',
      ] as const),
    authorityInterpretation:
      'server-snapshot-and-result-authority-with-client-side-view-models-and-selection',
  } as const)

export const LOGRES_GLOBAL_3024_QUESTS =
  Object.freeze({
    manager:
      'QuestManager',
    issueManager:
      'QuestIssueManager',
    keyClasses:
      Object.freeze([
        'QuestOne',
        'QuestChapterList',
        'QuestAccept',
        'QuestResultBase',
        'QuestBoard',
        'QuestRoomSelect',
        'MissionBoard',
      ] as const),
    requests:
      Object.freeze({
        accept:
          Object.freeze({
            name: 'C_GMCL_QUEST_ACCEPT_REQ',
            functionId: 2567234653,
            parameter:
              't_QuestAcceptRequestParam',
          } as const),
        retire:
          Object.freeze({
            name: 'C_GMCL_QUEST_RETIRE_REQ',
            functionId: 2266098243,
            parameter:
              't_QuestUID',
          } as const),
        acceptConditionCheck:
          'C_GMCL_QUEST_ACCEPT_CONDITION_CHECK',
        trophyCollect:
          'C_GMCL_QUEST_TROPHY_COLLECT_REQ',
        startVoyage:
          'C_GMCL_QUEST_START_VOYAGE',
        enchantAdd:
          'C_GMCL_QUEST_ENCHANT_ADD_REQ',
      } as const),
    statePushSequence:
      Object.freeze([
        'S_GMCL_QUEST_INFO_STATE_INIT',
        'S_GMCL_QUEST_INFO_STATE_BEGIN_EVENT',
        'S_GMCL_QUEST_INFO_STATE_BEGIN_POPUPINFO',
        'S_GMCL_QUEST_INFO_STATE_PROGRESS_START',
        'S_GMCL_QUEST_INFO_STATE_PROGRESS_UPDATE',
        'S_GMCL_QUEST_INFO_STATE_INTERMISSION',
        'S_GMCL_QUEST_INFO_STATE_RESULT',
        'S_GMCL_QUEST_INFO_STATE_RESULT_TROPHY',
        'S_GMCL_QUEST_INFO_STATE_STAMP_REWARD',
        'S_GMCL_QUEST_INFO_STATE_RETRY',
        'S_GMCL_QUEST_INFO_STATE_RETURN',
        'S_GMCL_QUEST_INFO_STATE_WAIT_FOR_END',
        'S_GMCL_QUEST_INFO_STATE_END_EVENT',
        'S_GMCL_QUEST_INFO_STATE_END_POPUPINFO',
        'S_GMCL_QUEST_INFO_STATE_END',
      ] as const),
    resultStateFunctionId:
      1638040888,
    managerMethods:
      Object.freeze([
        'sendQuestAccept',
        'sendQuestRetire',
        'sendNextQuestState',
        'sendQuestFieldInfo',
        'sendQuestEnchantAdd',
        'sendQuestRetryStateChange',
        'sendQuestAcceptConditionCheck',
        'recvQuestInfoBase',
        'recvQuestStateProgressUpdate',
      ] as const),
    authorityInterpretation:
      'server-authored-quest-state-machine-with-client-side-presentation-and-next-state-requests',
  } as const)

export const LOGRES_GLOBAL_3024_JOBS =
  Object.freeze({
    keyClasses:
      Object.freeze([
        'ChangeJob',
        'JobAbilityDetailWindow',
        'JobAbilityStatusChangeTable',
        'JobDetailWindow',
        'JobAbilitySrcTable',
        'JobBoardList',
        'JobInfoDictionary',
        'CommandSkillSelector',
        'SkillSelectorManager',
      ] as const),
    jobChange:
      Object.freeze({
        name: 'C_GMCL_JOB_CHANGE_REQ',
        functionId: 3865175023,
        generator:
          'generate_C_GMCL_JOB_CHANGE_REQ(Buffer&, t_ScriptUID const&, int, int)',
      } as const),
    jobChangeInfo:
      Object.freeze({
        name: 'S_GMCL_JOB_CHANGE_INFO',
        functionId: 587979822,
      } as const),
    serverTables:
      Object.freeze([
        'S_GMCL_JOB_ABILITY_STATUS_INFO',
        'S_GMCL_JOB_ABILITY_STATUS_INFO_DEVIDE_SEND_PARAM',
        'S_GMCL_NOTIFY_ITEM_EXP2LEVEL_TABLE',
        'S_GMCL_NOTIFY_SKILL_DERIVING_RATIO_TABLE',
        'S_GMCL_CHAR_LEVEL_MODIFY',
      ] as const),
    authorityInterpretation:
      'server-projected-job-level-and-ability-state-with-client-side-selection-and-display',
  } as const)

export const LOGRES_GLOBAL_3024_ECONOMY =
  Object.freeze({
    gacha:
      Object.freeze({
        operation:
          'GachaRpcOperation',
        list:
          Object.freeze({
            name: 'C_GMCL_GACHA_LIST_REQ',
            functionId: 3760465990,
          } as const),
        draw:
          Object.freeze({
            name: 'C_GMCL_GACHA_BUY_REQ',
            functionId: 1353764312,
            contract:
              'C_GMCL_GACHA_BUY_REQ(int, int)',
            clientMethod:
              'GachaRpcOperation::requestDraw(int, int, callback)',
          } as const),
        resultPush:
          Object.freeze({
            name:
              'S_GMCL_GACHA2_LOT_RESULT',
            functionId:
              1222842879,
          } as const),
        resultEnum:
          Object.freeze({
            SUCCESS: 0,
            FAILURE: 1,
          } as const),
      } as const),
    giftAccept:
      Object.freeze({
        name: 'C_GMCL_GIFT_ACCEPT_REQ',
        functionId: 3492392507,
      } as const),
    paymentResult:
      Object.freeze({
        SUCCESS: 0,
        FAILURE: 1,
      } as const),
    giftResultNames:
      Object.freeze([
        'SUCCESS',
        'ERROR_FULL',
        'ERROR_ITEM_LIMIT',
        'ERROR_MONEY_LIMIT',
        'ERROR_NOT_FOR_SELLING',
        'ERROR_UNKNOWN',
      ] as const),
    keyClasses:
      Object.freeze([
        'GiftPageWindow',
        'GachaDetailWindow',
        'GachaMainWindow',
        'GachaProductionWindow',
        'GachaResultWindow',
        'BoxGachaDetailWindow',
        'ShopPage',
        'ShopExtendInventory',
        'ShopRecoverEP',
        'PaymentPointConfirm',
      ] as const),
    authorityInterpretation:
      'server-authoritative-purchase-draw-payment-and-gift-results-with-client-side-catalog-and-production-ui',
  } as const)

export const LOGRES_GLOBAL_3024_PARTY =
  Object.freeze({
    manager: 'PartyManager',
    apply:
      Object.freeze({
        name: 'C_GMCL_APPLY_TO_PARTY',
        functionId: 760832940,
        contract:
          'C_GMCL_APPLY_TO_PARTY(uint, party_id_t, cuid_t)',
      } as const),
    invite:
      Object.freeze({
        name: 'C_GMCL_INVITE_TO_PARTY',
        functionId: 621099258,
        contract:
          'C_GMCL_INVITE_TO_PARTY(uint, party_id_t, cuid_t)',
      } as const),
    leave:
      Object.freeze({
        name: 'C_GMCL_PARTY_LEAVE_REQ',
        functionId: 4282329190,
        parameter:
          't_GmPartyUID',
      } as const),
    sync:
      Object.freeze({
        name: 'S_GMCL_PARTY_SYNC_PARTYINFO',
        functionId: 3807449958,
      } as const),
    separateMercenarySystem:
      true,
    authorityInterpretation:
      'server-synchronized-party-membership-with-client-side-manager-and-dialog-result-handling',
  } as const)

export const LOGRES_GLOBAL_3024_CLAN =
  Object.freeze({
    manager: 'ClanManager',
    rpc: 'ClanRPCInterface',
    create:
      Object.freeze({
        name: 'C_GMCL_CLAN_CREATE_CLAN_REQ',
        functionId: 2603760847,
        parameter:
          't_ClanConfig',
      } as const),
    apply:
      Object.freeze({
        name: 'C_GMCL_APPLY_TO_CLAN',
        functionId: 2183103050,
        contract:
          'C_GMCL_APPLY_TO_CLAN(uint, t_CUID)',
      } as const),
    leave:
      Object.freeze({
        name: 'C_GMCL_CLAN_LEAVE_CLAN_REQ',
        functionId: 2945183757,
      } as const),
    sync:
      Object.freeze({
        name: 'S_GMCL_CLAN_SYNC_CLANINFO',
        functionId: 2327358608,
      } as const),
    operations:
      Object.freeze([
        'requestCreateClan',
        'requestApplyToClan',
        'requestInviteToClan',
        'requestJoinToAnyClan',
        'requestKickClanMember',
        'requestClanMissionList',
        'requestChangeClanConfig',
        'requestGiveMasterAuthority',
      ] as const),
    serverProjection:
      Object.freeze([
        'S_GMCL_NOTIFY_CLAN_BOARD',
        'S_GMCL_NOTIFY_CLAN_EXP_TABLE',
        'S_GMCL_NOTIFY_CLAN_LEVEL',
        'S_GMCL_NOTIFY_CLAN_NAME',
        'S_GMCL_NOTIFY_CLAN_POINT',
      ] as const),
    authorityInterpretation:
      'server-authoritative-membership-config-missions-and-progression-with-local-cache-and-ui',
  } as const)

export const LOGRES_GLOBAL_3024_CHAT_MAIL =
  Object.freeze({
    chatSystem:
      'chat::ChatSystem',
    chatSend:
      Object.freeze({
        name: 'C_GMCL_CHAT_SEND_REQ',
        functionId: 1865766449,
        contract:
          'C_GMCL_CHAT_SEND_REQ(destination_t, string)',
      } as const),
    stampSend:
      Object.freeze({
        name: 'C_GMCL_STAMP_SEND_REQ',
        functionId: 3733035463,
      } as const),
    chatPush:
      Object.freeze({
        name: 'S_GMCL_CHAT',
        functionId: 218131023,
      } as const),
    receiveMail:
      Object.freeze({
        name: 'C_GMCL_RECEIVE_MAIL',
        functionId: 1729810893,
        generator:
          'generate_C_GMCL_RECEIVE_MAIL(Buffer&, uint, uint, mail_uid_t const&, mail_uid_t const&)',
      } as const),
    eraseMail:
      Object.freeze({
        name: 'C_GMCL_ERASE_MAIL',
        functionId: 3518080987,
        generator:
          'generate_C_GMCL_ERASE_MAIL(Buffer&, uint, uint, mail_uid_t const&, mail_uid_t const&)',
      } as const),
    messagePush:
      Object.freeze({
        name: 'S_GMCL_MESSAGE',
        functionId: 3088420669,
      } as const),
    messageTypes:
      Object.freeze([
        'chat::NormalMessageOne',
        'chat::StampMessageOne',
        'chat::DialogMessageOne',
      ] as const),
    groupOperations:
      Object.freeze([
        'C_GMCL_CREATE_CHATGROUP',
        'C_GMCL_LEAVE_CHATGROUP',
        'C_GMCL_INVITE_TO_CHAT_GROUP',
        'C_GMCL_UPDATE_CHAT_GROUP_ATTRIBUTES',
      ] as const),
    authorityInterpretation:
      'server-pushed-messaging-with-client-side-channel-group-direct-log-and-dialog-state',
  } as const)

export const LOGRES_GLOBAL_3024_BUNDLED_SYSTEM_CONFIG =
  Object.freeze({
    equipmentFilterScalars: 48,
    equipmentSortScalars: 126,
    equipmentTextScalars: 83,
    equipmentUiScalars: 6,
    fusionTextScalars: 78,
    fusionTutorialScalars: 7,
    gachaScalars: 44,
    garageFilterScalars: 27,
    garageSettingsScalars: 10,
    garageSortScalars: 12,
    garageTextScalars: 20,
    generalItemScalars: 24,
    giftScalars: 29,
    inventoryScalars: 5,
    missionScalars: 18,
    questScalars: 202,
    rankingScalars: 151,
    shopScalars: 16,
    sixthSenseUiScalars: 149,
    clanScalars: 27,
    chatOptionScalars: 13,
    chatTextScalars: 44,
    eventSettingScalars: 190,
  } as const)

export const LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED =
  Object.freeze([
    'semantic field names for several positional integer protocol constructor arguments',
    'complete server-side validation formulas and database constraints',
    'historical production catalog contents for shops and gachas beyond bundled UI/config evidence',
    'historical quest source payload corpus beyond client-side schema, state machine and bundled text/config',
    'historical item source payload corpus and exact inventory contents',
    'historical clan, party, friend and chat server-side persistence policies',
    'mail payload field semantics beyond recovered request signatures and server message boundary',
  ] as const)
