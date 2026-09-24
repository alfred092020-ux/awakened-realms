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

export type LogresAssetTransform =
  | 'DDS_TO_PNG_HYDRATION'
  | 'PNG_COPY'

export interface LogresAssetLineageRecord {
  readonly key: string
  readonly sourceEntry: string | null
  readonly sourceSha256: string | null
  readonly sourceProvenance: string
  readonly transform: LogresAssetTransform | null
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

function globalIndexPassRecord(
  key: string,
  sourceEntry: string,
  sourceSha256: string,
  transform: LogresAssetTransform,
  runtime: {
    readonly key: string
    readonly url: string
  },
): LogresAssetLineageRecord {
  return Object.freeze({
    key,
    sourceEntry,
    sourceSha256,
    sourceProvenance:
      'CONFIRMED ORIGINAL GLOBAL RUNTIME ASSET INDEX',
    transform,
    runtimeKey: runtime.key,
    runtimeUrl: runtime.url,
    status: 'PASS',
    note:
      'Global runtime-asset-index source identity, exact transform class and current runtime binding are all present.',
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
      globalIndexPassRecord(
        'title-background',
        'gui/title/title_back.dds',
        'd5cd1b816d3116a197ae5d1b4faa7648c37b93bf1cb5b604adf76aa7ddf47060',
        'DDS_TO_PNG_HYDRATION',
        LOGRES_ASSETS.titleBackground,
      ),
      globalIndexPassRecord(
        'title-logo',
        'gui/title/effect/png/logo00.png',
        '41a5dc4cfe16dfb9725f067208f705814ad69f366d8ecc350ff8e493ddabf7fe',
        'PNG_COPY',
        LOGRES_ASSETS.titleLogo,
      ),
      globalIndexPassRecord(
        'title-base',
        'gui/title/title_base01.dds',
        '7cf76d845ed76a64f7091e62b20efd538aa7968659a96238dfc9c65a4162df3a',
        'DDS_TO_PNG_HYDRATION',
        LOGRES_ASSETS.titleBase,
      ),
      globalIndexPassRecord(
        'title-start',
        'gui/title/title_ok.png',
        'b8048b804cca019c14a16936ef9d587c20a36cda86812cf279ec6862777a773a',
        'PNG_COPY',
        LOGRES_ASSETS.titleStart,
      ),
      globalIndexPassRecord(
        'world-select-01',
        'gui/title/world_select01.png',
        '0cb475b93b3dd510801c208c5950961b2419bba5316871d65a19c0ca975612be',
        'PNG_COPY',
        LOGRES_ASSETS.worldSelect,
      ),
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
