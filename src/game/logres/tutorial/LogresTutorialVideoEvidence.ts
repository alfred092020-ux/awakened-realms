export type LogresEvidenceLabel =
  | 'CONFIRMED ORIGINAL'
  | 'SUPPORTED INFERENCE'
  | 'RECONSTRUCTED'
  | 'UNRESOLVED'

export interface LogresTutorialVisualLandmark {
  id: string
  label: LogresEvidenceLabel
}

export interface LogresTutorialStageEvidence {
  order: number
  id: string
  label: LogresEvidenceLabel
}

export const LOGRES_TUTORIAL_VIDEO_EVIDENCE =
  Object.freeze({
    provenance:
      'USER_SUPPLIED_ORIGINAL_GAMEPLAY_VIDEO',
    mapIdentity: {
      mapId: null,
      label:
        'UNRESOLVED' as const,
    },
    candidatePriority: [
      {
        mapId:
          '001_000_00001',
        label:
          'SUPPORTED INFERENCE' as const,
        reason:
          'Live semantic map-reference evidence links this recovered map id to quest workflow context. Visual match is still required.',
      },
    ],
    landmarks: [
      {
        id:
          'bright-grass-field',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'tiered-stone-cliffs',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'lower-water-edge',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'large-tree-lower-left',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'curled-vine-cluster-lower-right',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'multiple-level-1-field-enemies',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        id:
          'armored-male-npc-near-player-start',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
    ] satisfies
      readonly LogresTutorialVisualLandmark[],
    stages: [
      {
        order: 1,
        id:
          'npc-first-contact',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        order: 2,
        id:
          'field-control-visible',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        order: 3,
        id:
          'quest-start-win-battle',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        order: 4,
        id:
          'guided-field-encounter',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        order: 5,
        id:
          'battle-entry',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
      {
        order: 6,
        id:
          'first-attack-guidance',
        label:
          'CONFIRMED ORIGINAL' as const,
      },
    ] satisfies
      readonly LogresTutorialStageEvidence[],
  })

export function logresTutorialStageIds():
  readonly string[] {
  return LOGRES_TUTORIAL_VIDEO_EVIDENCE
    .stages
    .map(
      ({ id }) => id,
    )
}
