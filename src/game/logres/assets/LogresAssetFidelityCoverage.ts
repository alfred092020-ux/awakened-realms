import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
} from '../tutorial/LogresTutorialHudEvidence'
import {
  LOGRES_ASSETS,
} from '../ui/LogresRuntimeAssets'

export const LOGRES_ASSET_FIDELITY_SCHEMA_VERSION =
  'asset-fidelity-v1' as const

export type LogresAssetLineageStatus =
  | 'PASS'
  | 'EVIDENCE_CEILING'

export interface LogresAssetLineageRecord {
  readonly key: string
  readonly sourceEntry: string | null
  readonly sourceSha256: string | null
  readonly sourceProvenance: string
  readonly transform: string | null
  readonly runtimeKey: string | null
  readonly runtimeUrl: string | null
  readonly status: LogresAssetLineageStatus
  readonly note: string
}

function passRecord(
  key: string,
  evidence: {
    readonly sourceEntry: string
    readonly sourceSha256: string
    readonly sourceLabel: string
    readonly runtimeUrl: string
  },
  runtimeKey: string | null = null,
): LogresAssetLineageRecord {
  return Object.freeze({
    key,
    sourceEntry: evidence.sourceEntry,
    sourceSha256: evidence.sourceSha256,
    sourceProvenance: evidence.sourceLabel,
    transform: 'DDS_TO_PNG_HYDRATION',
    runtimeKey,
    runtimeUrl: evidence.runtimeUrl,
    status: 'PASS',
    note:
      'Recovered source identity, deterministic DDS-to-PNG transform and runtime binding are all present.',
  })
}

export const LOGRES_ASSET_FIDELITY_COVERAGE =
  Object.freeze({
    schemaVersion:
      LOGRES_ASSET_FIDELITY_SCHEMA_VERSION,
    records: Object.freeze([
      passRecord(
        'tutorial-field-menu',
        LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.fieldMenu,
      ),
      passRecord(
        'tutorial-quest-start-text',
        LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartText,
        LOGRES_ASSETS.tutorialQuestStartText.key,
      ),
      passRecord(
        'tutorial-quest-start-background',
        LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.questStartBackground,
        LOGRES_ASSETS.tutorialQuestStartBackground.key,
      ),
      Object.freeze({
        key: 'title-background',
        sourceEntry: 'title_back.dds',
        sourceSha256: null,
        sourceProvenance: 'CONFIRMED ORIGINAL RESOURCE NAME',
        transform: 'DDS_TO_PNG_HYDRATION',
        runtimeKey:
          LOGRES_ASSETS.titleBackground.key,
        runtimeUrl:
          LOGRES_ASSETS.titleBackground.url,
        status: 'EVIDENCE_CEILING' as const,
        note:
          'Runtime binding is known, but this coverage surface does not yet expose a per-entry original source hash.',
      }),
      Object.freeze({
        key: 'title-logo',
        sourceEntry: 'logo00.dds',
        sourceSha256: null,
        sourceProvenance: 'CONFIRMED ORIGINAL RESOURCE NAME',
        transform: 'DDS_TO_PNG_HYDRATION',
        runtimeKey:
          LOGRES_ASSETS.titleLogo.key,
        runtimeUrl:
          LOGRES_ASSETS.titleLogo.url,
        status: 'EVIDENCE_CEILING' as const,
        note:
          'Runtime binding is known, but this coverage surface does not yet expose a per-entry original source hash.',
      }),
    ] as const),
    policy: Object.freeze({
      passRequirement:
        'PASS requires source hash, transform classification and a concrete runtime binding URL; runtime keys are recorded where the runtime exposes one.',
      evidenceCeilingRule:
        'Missing per-entry source identity cannot be promoted to PASS even when a runtime asset exists.',
      provenanceRule:
        'Original, inferred and reconstructed assets remain distinct; current-JP-only derivatives cannot establish historical Global provenance.',
    }),
  } as const)

export function validateLogresAssetFidelityCoverage(
  records:
    readonly LogresAssetLineageRecord[] =
      LOGRES_ASSET_FIDELITY_COVERAGE.records,
): void {
  const keys = new Set<string>()

  for (const record of records) {
    if (!record.key.trim()) {
      throw new Error('Asset fidelity record key must be non-empty')
    }
    if (keys.has(record.key)) {
      throw new Error(
        `Duplicate asset fidelity record key: ${record.key}`,
      )
    }
    keys.add(record.key)

    if (record.status === 'PASS') {
      if (
        !record.sourceEntry ||
        !record.sourceSha256 ||
        !/^[0-9a-f]{64}$/i.test(record.sourceSha256) ||
        !record.transform ||
        !record.runtimeUrl
      ) {
        throw new Error(
          `PASS asset lineage is incomplete: ${record.key}`,
        )
      }
      if (
        record.sourceProvenance.includes('CURRENT_JP')
      ) {
        throw new Error(
          `Historical Global PASS cannot rely on current-JP-only provenance: ${record.key}`,
        )
      }
    }

    if (
      record.status === 'EVIDENCE_CEILING' &&
      record.sourceSha256 !== null
    ) {
      throw new Error(
        `Evidence ceiling record unexpectedly has complete source identity: ${record.key}`,
      )
    }
  }
}
