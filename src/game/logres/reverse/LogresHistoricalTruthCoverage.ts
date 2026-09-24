import {
  LOGRES_GLOBAL_3024_BOOT_SOURCE,
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../onboarding/LogresGlobal3024BootEvidence'
import {
  LOGRES_GLOBAL_3024_FIELD_SOURCE,
  LOGRES_GLOBAL_3024_FIELD_MOVEMENT,
} from '../field/LogresGlobal3024FieldEvidence'
import {
  LOGRES_GLOBAL_3024_BATTLE_SOURCE,
  LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES,
} from '../battle/LogresGlobal3024BattleEvidence'
import {
  LOGRES_GLOBAL_3024_SYSTEMS_SOURCE,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from '../systems/LogresGlobal3024SystemsEvidence'
import {
  LOGRES_GLOBAL_3024_ASSET_SOURCE,
} from '../assets/LogresGlobal3024AssetEvidence'
import {
  LOGRES_TUTORIAL_VIDEO_EVIDENCE,
} from '../tutorial/LogresTutorialVideoEvidence'
import {
  LOGRES_RENDERER_PROOF_MAP_ID,
  LOGRES_RENDERER_PROOF_ROLE,
} from '../field/LogresRendererProofAssets'
import {
  LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES,
  LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS,
} from './LogresAssetBehaviorBindingEvidence'

export const LOGRES_HISTORICAL_TRUTH_SCHEMA =
  'historical-truth-v1' as const

export const LOGRES_HISTORICAL_EVIDENCE_PRECEDENCE =
  Object.freeze([
    'GLOBAL_3_0_24',
    'ORIGINAL_GLOBAL_GAMEPLAY',
    'CURRENT_JP_REFERENCE',
    'RECONSTRUCTED',
  ] as const)

export type LogresHistoricalTruthDomain =
  | 'BOOT'
  | 'TUTORIAL'
  | 'FIELD'
  | 'NPC_ENCOUNTER'
  | 'BATTLE'
  | 'SYSTEMS'
  | 'ASSETS'
  | 'SERVER_BOUNDARY'

export type LogresHistoricalTruthConfidence =
  | 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24'
  | 'CONFIRMED_ORIGINAL_VIDEO'
  | 'SUPPORTED_INFERENCE'
  | 'RECONSTRUCTED'
  | 'UNKNOWN'

export interface LogresHistoricalTruthClaim {
  readonly id: string
  readonly domain: LogresHistoricalTruthDomain
  readonly statement: string
  readonly confidence: LogresHistoricalTruthConfidence
  readonly evidenceRefs: readonly string[]
  readonly evidenceCeiling: string | null
  readonly contradictions: readonly string[]
}

export const LOGRES_RELEASE_CRITICAL_HISTORICAL_DOMAINS =
  Object.freeze([
    'BOOT',
    'TUTORIAL',
    'FIELD',
    'NPC_ENCOUNTER',
    'BATTLE',
    'SYSTEMS',
    'ASSETS',
    'SERVER_BOUNDARY',
  ] as const satisfies readonly LogresHistoricalTruthDomain[])

export const LOGRES_RELEASE_CRITICAL_HISTORICAL_CLAIMS =
  Object.freeze([
    Object.freeze({
      id: 'global-client-identity',
      domain: 'BOOT',
      statement:
        'The recovered Global client evidence is version 3.0.24 and is anchored to immutable client/native hashes.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:apk-sha256:${LOGRES_GLOBAL_3024_ASSET_SOURCE.apkSha256}`,
        `global:libgame-sha256:${LOGRES_GLOBAL_3024_BOOT_SOURCE.libgameArm64Sha256}`,
      ]),
      evidenceCeiling: null,
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'terms-gate-launch-order',
      domain: 'BOOT',
      statement:
        `The evidenced launch gate is ${LOGRES_GLOBAL_3024_TERMS_GATE.launchOrder}; the exact retired hosted terms page remains unresolved.`,
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:launch-video-sha256:${LOGRES_GLOBAL_3024_BOOT_SOURCE.launchVideoSha256}`,
        `global:agreement-scene:${LOGRES_GLOBAL_3024_TERMS_GATE.agreementScene}`,
      ]),
      evidenceCeiling:
        'The exact retired hosted agreement page content is unresolved.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'world-select-first-run-condition',
      domain: 'BOOT',
      statement:
        'A native world-selector exists, but the captured first-run path does not prove that it was mandatory for every historical first-run session.',
      confidence: 'SUPPORTED_INFERENCE',
      evidenceRefs: Object.freeze([
        `global:native-scene:${LOGRES_GLOBAL_3024_WORLD_SELECTION.nativeScene}`,
        `original-video:observation:${LOGRES_GLOBAL_3024_WORLD_SELECTION.launchVideoObservation}`,
      ]),
      evidenceCeiling:
        'The exact historical server/account condition that caused world selection to appear is unresolved.',
      contradictions: Object.freeze([
        'Native world-selector symbols exist while the captured launch video contains no world selector between Terms and gender.',
      ]),
    }),
    Object.freeze({
      id: 'opening-tutorial-map-identity',
      domain: 'TUTORIAL',
      statement:
        'The opening tutorial field family is visually evidenced, but its exact historical map ID is not confirmed.',
      confidence: 'UNKNOWN',
      evidenceRefs: Object.freeze([
        `original-video:provenance:${LOGRES_TUTORIAL_VIDEO_EVIDENCE.provenance}`,
        `global:renderer-proof-map:${LOGRES_RENDERER_PROOF_MAP_ID}`,
      ]),
      evidenceCeiling:
        `The video map identity is UNRESOLVED; ${LOGRES_RENDERER_PROOF_MAP_ID} is explicitly ${LOGRES_RENDERER_PROOF_ROLE}, not proof of tutorial assignment.`,
      contradictions: Object.freeze([
        'Recovered map packages and geometric candidates exist, but no primary evidence binds the exact tutorial quest instance to one map ID.',
      ]),
    }),
    Object.freeze({
      id: 'field-movement-boundary',
      domain: 'FIELD',
      statement:
        `Global field evidence identifies ${LOGRES_GLOBAL_3024_FIELD_MOVEMENT.pathfinder} and the ${LOGRES_GLOBAL_3024_FIELD_MOVEMENT.outgoingRequest} movement boundary.`,
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:field-libgame:${LOGRES_GLOBAL_3024_FIELD_SOURCE.libgameArm64Sha256}`,
        `global:movement-request:${LOGRES_GLOBAL_3024_FIELD_MOVEMENT.outgoingRequest}`,
      ]),
      evidenceCeiling:
        'Confirmed client movement/path/projection surfaces do not reveal every retired server-side validation rule.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'tutorial-npc-presence',
      domain: 'NPC_ENCOUNTER',
      statement:
        'The original tutorial recording confirms an armored male NPC near the player start, without revealing a historical NPC ID or name.',
      confidence: 'CONFIRMED_ORIGINAL_VIDEO',
      evidenceRefs: Object.freeze([
        `original-video:provenance:${LOGRES_TUTORIAL_VIDEO_EVIDENCE.provenance}`,
        'original-video:landmark:armored-male-npc-near-player-start',
      ]),
      evidenceCeiling:
        'Historical NPC identity, actor package binding and dialogue payload remain unresolved.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'battle-server-message-surface',
      domain: 'BATTLE',
      statement:
        'Global 3.0.24 contains a server-driven battle message surface including battle initialization and result messages.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:battle-libgame:${LOGRES_GLOBAL_3024_BATTLE_SOURCE.libgameArm64Sha256}`,
        `global:battle-message:${LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES[0]}`,
        `global:battle-message:${LOGRES_GLOBAL_3024_BATTLE_SERVER_MESSAGES.at(-1)}`,
      ]),
      evidenceCeiling:
        'Client-observed message surfaces do not recover the retired server implementation or every outcome formula.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'systems-client-protocol-surface',
      domain: 'SYSTEMS',
      statement:
        'Global 3.0.24 exposes native/protocol surfaces for item, quest, job, economy and social systems.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:systems-libgame:${LOGRES_GLOBAL_3024_SYSTEMS_SOURCE.libgameArm64Sha256}`,
        `global:function-id-count:${LOGRES_GLOBAL_3024_SYSTEMS_SOURCE.numericFunctionIdCount}`,
      ]),
      evidenceCeiling:
        LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED.find(
          (value) => value.includes('server-side validation formulas'),
        ) ?? 'Complete retired server-side formulas remain unresolved.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'global-asset-bootstrap-corpus',
      domain: 'ASSETS',
      statement:
        'Recovered Global packaged-asset metadata is anchored to the Global APK and evidence-artifact hashes.',
      confidence: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      evidenceRefs: Object.freeze([
        `global:apk-sha256:${LOGRES_GLOBAL_3024_ASSET_SOURCE.apkSha256}`,
        `global:asset-evidence-sha256:${LOGRES_GLOBAL_3024_ASSET_SOURCE.evidenceArtifactSha256}`,
        `global:bootstrap-manifest-sha256:${LOGRES_GLOBAL_3024_ASSET_SOURCE.bootstrapMemberManifestSha256}`,
      ]),
      evidenceCeiling:
        'Packaged asset presence does not by itself prove a dynamic retired-server asset-selection decision.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'field-map-package-tutorial-assignment',
      domain: 'ASSETS',
      statement:
        `The exact Global package ${LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.fieldMapPackage.globalPath} is recovered, but its historical tutorial-area assignment is not claimed.`,
      confidence: 'UNKNOWN',
      evidenceRefs: Object.freeze([
        `global:resource:${LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.fieldMapPackage.globalPath}`,
      ]),
      evidenceCeiling:
        LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS.find(
          (value) => value.includes('tutorial-area assignment'),
        ) ?? 'Historical tutorial-area assignment remains unresolved.',
      contradictions: Object.freeze([] as const),
    }),
    Object.freeze({
      id: 'retired-server-internal-semantics',
      domain: 'SERVER_BOUNDARY',
      statement:
        'Retired server internals beyond client-observed protocol/state boundaries remain unknown and are reconstructed only where explicitly labeled.',
      confidence: 'UNKNOWN',
      evidenceRefs: Object.freeze([
        `global:systems-libgame:${LOGRES_GLOBAL_3024_SYSTEMS_SOURCE.libgameArm64Sha256}`,
      ]),
      evidenceCeiling:
        'The retired authoritative server binaries/database/runtime are not present in the recovered client corpus.',
      contradictions: Object.freeze([
        'Current-JP behavior may inform reconstruction but cannot replace missing Global server evidence.',
      ]),
    }),
  ] as const satisfies readonly LogresHistoricalTruthClaim[])

function requireText(value: string, label: string): void {
  if (!value.trim()) throw new Error(`${label} must be non-empty`)
}

export function assertLogresHistoricalTruthCoverage(
  claims: readonly LogresHistoricalTruthClaim[],
): void {
  const ids = new Set<string>()
  const domains = new Set<LogresHistoricalTruthDomain>()

  for (const claim of claims) {
    requireText(claim.id, 'Historical claim id')
    requireText(claim.statement, `Historical claim ${claim.id} statement`)
    if (ids.has(claim.id)) {
      throw new Error(`Duplicate historical claim id: ${claim.id}`)
    }
    ids.add(claim.id)
    domains.add(claim.domain)

    const refs = claim.evidenceRefs.filter((value) => value.trim())
    const hasGlobal = refs.some((value) => value.startsWith('global:'))
    const hasOriginalVideo = refs.some((value) => value.startsWith('original-video:'))
    const hasCurrentJp = refs.some((value) => value.startsWith('current-jp:'))

    if (
      claim.confidence === 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24' &&
      (!refs.length || !hasGlobal)
    ) {
      throw new Error(
        `Confirmed Global historical claim ${claim.id} requires explicit Global evidence`,
      )
    }
    if (
      claim.confidence === 'CONFIRMED_ORIGINAL_VIDEO' &&
      (!refs.length || !hasOriginalVideo)
    ) {
      throw new Error(
        `Confirmed original-video claim ${claim.id} requires original gameplay evidence`,
      )
    }
    if (
      claim.confidence === 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24' &&
      hasCurrentJp &&
      !hasGlobal
    ) {
      throw new Error(
        `Current-JP-only evidence cannot confirm Global historical claim ${claim.id}`,
      )
    }
    if (
      claim.confidence === 'SUPPORTED_INFERENCE' &&
      (!refs.length || !claim.evidenceCeiling?.trim())
    ) {
      throw new Error(
        `Supported inference ${claim.id} requires evidence and an explicit ceiling`,
      )
    }
    if (
      claim.confidence === 'UNKNOWN' &&
      !claim.evidenceCeiling?.trim()
    ) {
      throw new Error(
        `Unknown historical claim ${claim.id} requires an explicit evidence ceiling`,
      )
    }
    if (
      hasGlobal &&
      hasCurrentJp &&
      claim.confidence !== 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24' &&
      claim.contradictions.length === 0
    ) {
      throw new Error(
        `Mixed-version historical claim ${claim.id} must record contradictions explicitly`,
      )
    }
  }

  for (const domain of LOGRES_RELEASE_CRITICAL_HISTORICAL_DOMAINS) {
    if (!domains.has(domain)) {
      throw new Error(`Missing release-critical historical domain: ${domain}`)
    }
  }
}
