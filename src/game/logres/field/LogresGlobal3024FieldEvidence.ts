export const LOGRES_GLOBAL_3024_FIELD_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_SURFACE_COUNTS =
  Object.freeze({
    fieldConstantMethods: 23,
    gameFieldSceneMethods: 34,
    simpleAStarMethods: 3,
    movePathMethods: 4,
    moveLinearMethods: 2,
    moverComplyPathMethods: 6,
    encounterMethods: 8,
    encounterBaseMethods: 4,
    battleSymbolMethods: 19,
    npcDialogueMethods: 37,
    warpMediatorMethods: 21,
    warpObjectMethods: 14,
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_RENDERER =
  Object.freeze({
    scene:
      'ReleaseScene_GameField',
    touchBoundary:
      'ReleaseScene_GameField::touchEnded',
    resourceFamilies:
      Object.freeze([
        'MapTerrainResource',
        'MapInfoResource<InfoChipBin>',
        'MapInfoResource<InfoObjectBin>',
        'MapInfoResource<InfoBorderBin>',
        'MapInfoResource<InfoShadowBin>',
      ] as const),
    coordinateSystem:
      Object.freeze([
        'FieldConstant::coordToIndex',
        'FieldConstant::indexToCoord',
        'FieldConstant::coordToScreen',
        'FieldConstant::coordToPosition',
        'FieldConstant::coordToPosition3',
        'FieldConstant::positionToCoord',
        'FieldConstant::positionToCoord3',
        'FieldConstant::depthToZ',
        'FieldConstant::tileContains',
        'FieldConstant::centeringOfTile',
      ] as const),
    sceneResponsibilities:
      Object.freeze([
        'addTerrain',
        'buildLayerForScene',
        'updateField',
        'updateTargetTrace',
        'updateWeather',
        'updateTutorial',
        'onWarpBegan',
        'onWarpInfoReceived',
        'onWarpEnded',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_MOVEMENT =
  Object.freeze({
    pathfinder:
      'pathfinding::SimpleAStar',
    pathMover:
      'MovePathInitializer',
    linearMover:
      'MoveLinearInitializer',
    pathConsumer:
      'MoverComplyPath',
    outgoingRequest:
      'C_GMCL_CHAR_MOVE_REQ',
    outgoingRequestFields:
      Object.freeze([
        'speed',
        'areaUID',
        'startMapPos',
        'endMapPos',
        'gridCoordPath',
      ] as const),
    serverProjection:
      'S_GMCL_CHAR_MOVE_REQ',
    authorityInterpretation:
      'client-computes-path-server-projects-movement',
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_ENTITIES =
  Object.freeze({
    npcAppear:
      'S_GMCL_NPC_APPEAR',
    npcServerFields:
      Object.freeze([
        'ObjectUID',
        'name',
        'modelVolume',
        'areaUID',
        'mapPos',
        'icons',
        'appearReason',
        'npcCanTalkRange',
      ] as const),
    enemyAppear:
      'S_GMCL_ENEMY_APPEAR',
    enemyServerFields:
      Object.freeze([
        'ObjectUID',
        'modelVolume',
        'areaUID',
        'mapPos',
        'icons',
        'appearReason',
        'activeEnemyParam',
      ] as const),
    dialogueWindow:
      'NpcDialogueWindow',
    talkResponse:
      'C_GMCL_CHAR_TALK_REQ_Response',
    dialogueAnswerResponse:
      'C_GMCL_POST_DIALOG_ANSWER_Response',
    authorityInterpretation:
      'server-projected-field-objects',
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_ENCOUNTER =
  Object.freeze({
    system:
      'character::encounter::Encounter',
    base:
      'character::encounter::EncounterBase',
    shapes:
      Object.freeze([
        'character::encounter::shape::Circle',
        'character::encounter::shape::Rect',
      ] as const),
    characterUpdateHook:
      'character::Character::updateEncounter',
    battleSymbol:
      'character::BattleSymbol',
    battleEntryResponse:
      'C_GMCL_BATTLE_ENTRY_REQ_Response',
    partyMemberEncounter:
      'S_GMCL_BATTLE_PARTY_MEMBER_ENCOUNT',
    fieldBattleEffectAppear:
      'S_GMCL_FIELD_BATTLE_EFFECT_APPEAR',
    fieldBattleEffectUpdate:
      'S_GMCL_FIELD_BATTLE_EFFECT_UPDATE',
    authorityInterpretation:
      'geometric-client-detection-with-server-battle-entry-boundary',
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_WARP =
  Object.freeze({
    mediator:
      'warp::WarpMediator',
    object:
      'warp::WarpObject',
    states:
      Object.freeze([
        'NotWarpState',
        'WarpInState',
        'WarpInfoReceivedState',
        'WarpOutState',
        'WarpStopState',
      ] as const),
    serverSequence:
      Object.freeze([
        'S_GMCL_WARP',
        'S_GMCL_AREA_ENTER',
        'S_GMCL_WARP_FINISH',
      ] as const),
    observers:
      Object.freeze([
        'onWarpBegan',
        'onWarpInfoReceived',
        'onWarpEnded',
      ] as const),
    loadingScene:
      'ReleaseScene_Loading',
    authorityInterpretation:
      'server-mediated-stateful-area-transition',
  } as const)

export const LOGRES_GLOBAL_3024_FIELD_UNRESOLVED =
  Object.freeze([
    'exact server collision rejection rules beyond client path graph and static map geometry',
    'exact NPC dialogue payload text and branches for every tutorial step',
    'exact first-tutorial enemy encounter radius and shape values',
    'exact first Millennium Tree static map ID',
    'exact server battle-entry eligibility formula',
  ] as const)
