export const LOGRES_ASSET_BEHAVIOR_BINDER_PROVENANCE =
  'MUIUE_GLOBAL_ASSET_BEHAVIOR_BINDER_WITH_EXPLICIT_AUTHORITY' as const

export const LOGRES_ASSET_BEHAVIOR_BINDER_SOURCES =
  Object.freeze({
    semanticLiftSha256:
      'd215de8911416c4dab1185d80b0bc2e163c2f794d7d9f3a1253fc18a11383de5',
    resourceSemanticGraphSha256:
      'fdd4921dbab864840c1106a5ff2196da2c57b29a5517eca0e4a603a1e1f25ab3',
    mapGenealogySha256:
      'dbec39a300071ef2f8b30710948fd34de5bb52f010b6d6b05fad13e342dd13a9',
    protocolSchemaSha256:
      '9e9583da01db8aa4a7c808397cbf740114469902862bc5984631bbb6815a1f16',
    stateMachineSha256:
      '9c0348e02e6ea75986e6a08d5fdbb9c63329958df54ed308cb573eb135e12e7a',
  } as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_COUNTS =
  Object.freeze({
    semanticFunctionsExamined: 16379,
    semanticResourceCandidateFunctions: 468,
    nativeResourcePatterns: 910,
    directGlobalFunctionPatternBindings: 587,
    directGlobalPatternsBound: 501,
    exactGlobalResourceLineage: 14,
    changedPathLineageCandidates: 15,
    directBoundProtocolMessages: 0,
    directBoundStateTransitions: 1,
    verticalRolesWithDirectBindings: 7,
  } as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_VERTICAL_COUNTS =
  Object.freeze({
    titleUi: 56,
    playerActor: 4,
    fieldMap: 12,
    npcEnemyEncounter: 3,
    battle: 22,
    audioBgmSe: 11,
    rewardResult: 40,
  } as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_DIRECT_EXAMPLES =
  Object.freeze([
    Object.freeze({
      function: 'lfs::GameInformation::initializeForPreBeginGame()',
      resource: 'avatar/scale.json',
      role: 'player_actor',
      stateTransition: 'CHARACTER_LIST -> PREBEGIN_INIT',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN',
    }),
    Object.freeze({
      function: 'lfs::AgreementWebView::onEnter()',
      resource: 'gui/title/image9Slice/title_base.png',
      role: 'title_ui',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN',
    }),
    Object.freeze({
      function: 'lfs::TransitionEffectBattleIn::init()',
      resource: 'effect/transiton/encount_00.png',
      role: 'npc_enemy_encounter+battle',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN',
    }),
    Object.freeze({
      function: 'lfs::BoutBG::onEnter()',
      resource: 'battle/field/bfd_%03d_%03d.png',
      role: 'field_map+battle',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN',
    }),
    Object.freeze({
      function: 'lfs::BackgroundMusicResource::createFilePath(...)',
      resource: '.ogg',
      role: 'audio_bgm_se',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL',
    }),
    Object.freeze({
      function: 'lfs::QuestResultStamp::loadCompleteResource()',
      resource: 'gui/quest/effect/result/stamp_complete.lfla',
      role: 'reward_result',
      authority: 'CONFIRMED_GLOBAL_FUNCTION_RESOURCE_LITERAL_AND_GRAPH_PATTERN',
    }),
  ] as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES =
  Object.freeze({
    globalBgm: Object.freeze({
      globalPath: 'sound/bgm/000_000_00001.ogg',
      currentJpPath: 'sound/bgm/000_000_00002.ogg',
      relation: 'EXACT_BYTES_LINEAGE_RENAMED',
    }),
    globalSe: Object.freeze({
      globalPath: 'sound/se/100_000_00001.wav',
      currentJpPath: 'sound/se/100_000_00001.wav',
      relation: 'EXACT_BYTES_LINEAGE_SAME_PATH',
    }),
    battlePackage: Object.freeze({
      globalPath: 'Battle.mbn',
      currentJpPath: 'gui/Battle.mbn',
      relation: 'EXACT_BYTES_LINEAGE_RENAMED',
    }),
    fieldMapPackage: Object.freeze({
      globalPath: 'map-002/002_000_00001.mbn',
      currentJpPath: 'map/002_000_00001.mbn',
      relation: 'EXACT_BYTES_LINEAGE_RENAMED',
      historicalAreaAssignmentClaimed: false,
    }),
  } as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_AUTHORITY =
  Object.freeze({
    directFunctionLiteral: 1.0,
    exactGlobalResourceLineage: 1.0,
    changedPathLineageCandidate: 0.55,
    runtimePhaseCandidate: 0.35,
  } as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS =
  Object.freeze([
    'A Global function resource literal is a confirmed consumer-pattern binding; it does not prove which dynamic server-selected resource instance was used.',
    'Exact recovered Global resource bytes and manifest identity prove concrete Global presence and endpoint lineage, not surrounding server behavior.',
    'Same-path changed JP bytes remain lineage candidates and cannot replace historical Global bytes.',
    'Runtime phase/state joins derived from vertical taxonomy are candidate-only at score 0.35 and are not historical asset-selection claims.',
    'The Global 002_000_00001 package is proven, but its historical Global tutorial-area assignment is not claimed.',
    'Zero direct asset-consumer/protocol-handler overlap is preserved rather than manufacturing a protocol binding.',
  ] as const)

export const LOGRES_ASSET_BEHAVIOR_BINDER_ARTIFACT =
  Object.freeze({
    path: '/home/ubuntu/logres/artifacts/global-asset-behavior-bindings-20260924.json',
    sha256: 'a37faddba1c14e7e9fe2c8ca6e08e59dace41f0d9853b830fe2323f76c48d73c',
  } as const)
