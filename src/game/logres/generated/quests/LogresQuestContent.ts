import {
  createUnresolvedTutorialQuestInstance,
} from '../../server/LogresQuestInstanceAuthority'
import {
  LOGRES_GLOBAL_3024_QUESTS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../../systems/LogresGlobal3024SystemsEvidence'
import {
  LOGRES_TUTORIAL_VIDEO_EVIDENCE,
} from '../../tutorial/LogresTutorialVideoEvidence'
import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
} from '../../tutorial/LogresTutorialHudEvidence'

export const LOGRES_QUEST_CONTENT_SCHEMA_VERSION =
  'quest-content-v1' as const

export const LOGRES_QUEST_CONTENT_EVIDENCE = Object.freeze({
  acceptRequest:
    LOGRES_GLOBAL_3024_QUESTS.requests.accept,
  retireRequest:
    LOGRES_GLOBAL_3024_QUESTS.requests.retire,
  statePushSequence:
    LOGRES_GLOBAL_3024_QUESTS.statePushSequence,
  authorityInterpretation:
    LOGRES_GLOBAL_3024_QUESTS.authorityInterpretation,
  tutorialStages:
    LOGRES_TUTORIAL_VIDEO_EVIDENCE.stages,
  questStartText:
    LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartText,
  questStartBackground:
    LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartBackground,
  unresolvedHistoricalQuestCorpus:
    LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.filter(
      (value) => value.includes('historical quest source payload corpus'),
    ),
} as const)

export const LOGRES_QUEST_CONTENT_MANIFEST = Object.freeze({
  schemaVersion: LOGRES_QUEST_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze([
    Object.freeze({
      key: 'opening-tutorial',
      kind: 'RECONSTRUCTED_QUEST_BINDING' as const,
      existenceConfidence: 'CONFIRMED_ORIGINAL_VIDEO' as const,
      runtimeInstanceKey: 'opening-tutorial',
      historicalQuestRecordId: null,
      historicalQuestUid: null,
      historicalMapId: null,
      historicalRoomId: null,
      historicalPlayerSpawn: null,
      objectives: Object.freeze([] as const),
      encounters: Object.freeze([] as const),
      npcStateIds: Object.freeze([] as const),
      tutorialOverlayIds: Object.freeze([] as const),
      rules: Object.freeze({
        timeLimitSeconds: null,
        defeatLimit: null,
        battleCapacity: null,
        requiredPower: null,
      }),
      confirmedSequence: Object.freeze([
        'npc-first-contact',
        'field-control-visible',
        'quest-start-win-battle',
        'guided-field-encounter',
        'battle-entry',
        'first-attack-guidance',
      ] as const),
      presentationEvidence: Object.freeze({
        questStartTextSha256:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartText.sourceSha256,
        questStartBackgroundSha256:
          LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartBackground.sourceSha256,
        confidence: 'CONFIRMED_GLOBAL_3_0_24' as const,
      }),
      protocolEvidence: Object.freeze({
        acceptRequest:
          LOGRES_GLOBAL_3024_QUESTS.requests.accept.name,
        retireRequest:
          LOGRES_GLOBAL_3024_QUESTS.requests.retire.name,
        resultState:
          'S_GMCL_QUEST_INFO_STATE_RESULT',
        confidence: 'CONFIRMED_GLOBAL_3_0_24' as const,
      }),
      evidenceIds: Object.freeze([
        'tutorial-video:quest-start-win-battle',
        'tutorial-hud:quest_start.dds',
        'tutorial-hud:quest_bg00.dds',
        'protocol:C_GMCL_QUEST_ACCEPT_REQ',
        'runtime:createUnresolvedTutorialQuestInstance',
      ] as const),
    }),
  ] as const),
  evidenceCeilings: Object.freeze([
    'The opening tutorial is confirmed by original gameplay evidence, but its historical quest UID/record ID remains unresolved.',
    'The tutorial map assignment remains unresolved at quest-instance authority; static terrain evidence must not be promoted into historical quest state.',
    'Objectives, encounter IDs, NPC state IDs, overlays, limits and power requirements remain empty/null until primary evidence is recovered.',
  ] as const),
} as const)

export function createOpeningTutorialQuestContentInstance() {
  return createUnresolvedTutorialQuestInstance()
}
