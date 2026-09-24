import {
  LOGRES_PLAYER_ACTOR_PRESENTATION,
} from '../../field/LogresPlayerActorPresentation'
import {
  LOGRES_PLAYER_ACTOR_ASSETS,
} from '../../field/LogresPlayerActorRuntimeAssets'
import {
  LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
  LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE,
} from '../../encounter/ReconstructedLogresNpcDialogueAuthority'
import {
  LOGRES_TUTORIAL_VIDEO_EVIDENCE,
} from '../../tutorial/LogresTutorialVideoEvidence'

export const LOGRES_ACTOR_CONTENT_SCHEMA_VERSION =
  'actor-content-v1' as const

export type LogresActorContentConfidence =
  | 'CONFIRMED_GLOBAL_3_0_24'
  | 'CONFIRMED_ORIGINAL_VIDEO'
  | 'CURRENT_JP_REFERENCE_ONLY'
  | 'RECONSTRUCTED'
  | 'SUPPORTED_INFERENCE'
  | 'UNKNOWN'

export const LOGRES_ACTOR_CONTENT_MANIFEST = Object.freeze({
  schemaVersion: LOGRES_ACTOR_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze([
    Object.freeze({
      key: 'tutorial-armored-male-npc',
      kind: 'NPC' as const,
      presenceConfidence: 'CONFIRMED_ORIGINAL_VIDEO' as const,
      displayName: null,
      historicalCharacterRef: null,
      historicalNpcId: null,
      historicalRoleId: null,
      historicalDialoguePayload: null,
      presentation: Object.freeze({
        runtimeAssetKey: null,
        runtimeAssetUrl: null,
        confidence: 'UNKNOWN' as const,
        reason:
          'The original tutorial video confirms an armored male NPC near player start, but no recovered Global actor package has been mechanically bound to that NPC.',
      }),
      interaction: Object.freeze({
        requestMessage:
          LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY.requestMessage,
        responseHandler:
          LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY.responseHandler,
        dialogueWindow:
          LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY.dialogueWindow,
        protocolConfidence:
          'CONFIRMED_GLOBAL_3_0_24' as const,
        historicalDialoguePayloadConfidence:
          LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY.exactHistoricalDialoguePayload,
      }),
      reconstructedBinding: Object.freeze({
        npcKey:
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE.npcKey,
        scriptProvenance:
          LOGRES_RECONSTRUCTED_FIELD_GUIDE_DIALOGUE.provenance,
        confidence: 'RECONSTRUCTED' as const,
      }),
      evidenceIds: Object.freeze([
        'tutorial-video:armored-male-npc-near-player-start',
        'protocol:C_GMCL_CHAR_TALK_REQ',
        'runtime:reconstructed-millennium-tree-guide',
      ] as const),
    }),
    Object.freeze({
      key: 'created-player-avatar',
      kind: 'PLAYER' as const,
      presenceConfidence: 'CONFIRMED_GLOBAL_3_0_24' as const,
      displayName: null,
      historicalCharacterRef: null,
      historicalNpcId: null,
      historicalRoleId: null,
      historicalDialoguePayload: null,
      presentation: Object.freeze({
        runtimeMaleAssetKey:
          LOGRES_PLAYER_ACTOR_ASSETS.male.key,
        runtimeFemaleAssetKey:
          LOGRES_PLAYER_ACTOR_ASSETS.female.key,
        source:
          LOGRES_PLAYER_ACTOR_PRESENTATION.source,
        bodySelection:
          LOGRES_PLAYER_ACTOR_PRESENTATION.bodySelection,
        historicalGlobalBodyId:
          LOGRES_PLAYER_ACTOR_PRESENTATION.historicalGlobalBodyId,
        historicalGlobalEquipmentIds:
          LOGRES_PLAYER_ACTOR_PRESENTATION.historicalGlobalEquipmentIds,
        confidence:
          'CURRENT_JP_REFERENCE_ONLY' as const,
      }),
      interaction: null,
      reconstructedBinding: Object.freeze({
        worldPlacement:
          LOGRES_PLAYER_ACTOR_PRESENTATION.worldPlacement,
        confidence: 'RECONSTRUCTED' as const,
      }),
      evidenceIds: Object.freeze([
        'runtime:LogresPlayerActorPresentation',
        'runtime:LogresPlayerActorRuntimeAssets',
      ] as const),
    }),
  ] as const),
  evidenceCeilings: Object.freeze([
    'The tutorial NPC historical name, internal character reference, role ID and actor package remain unresolved.',
    'The player body/equipment art is a current-JP private derivative reference and is not confirmed historical Global artwork.',
    'Reconstructed guide dialogue must never be presented as recovered historical Global dialogue text.',
  ] as const),
} as const)

export const LOGRES_NPC_ACTOR_CONTENT_MANIFEST = Object.freeze({
  version: LOGRES_ACTOR_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze(
    LOGRES_ACTOR_CONTENT_MANIFEST.entries.filter(
      (entry) => entry.kind === 'NPC',
    ),
  ),
} as const)

export const LOGRES_PLAYER_ACTOR_CONTENT_MANIFEST = Object.freeze({
  version: LOGRES_ACTOR_CONTENT_SCHEMA_VERSION,
  entries: Object.freeze(
    LOGRES_ACTOR_CONTENT_MANIFEST.entries.filter(
      (entry) => entry.kind === 'PLAYER',
    ),
  ),
} as const)

export const LOGRES_ACTOR_CONTENT_EVIDENCE = Object.freeze({
  tutorialNpcLandmark:
    LOGRES_TUTORIAL_VIDEO_EVIDENCE.landmarks.find(
      ({ id }) => id === 'armored-male-npc-near-player-start',
    ) ?? null,
  firstContactStage:
    LOGRES_TUTORIAL_VIDEO_EVIDENCE.stages.find(
      ({ id }) => id === 'npc-first-contact',
    ) ?? null,
  npcDialogueBoundary:
    LOGRES_NPC_DIALOGUE_EVIDENCE_BOUNDARY,
} as const)
