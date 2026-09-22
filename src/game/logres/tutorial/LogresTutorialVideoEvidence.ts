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

export interface LogresTutorialMapCandidateEvidence {
  mapId: string
  label: LogresEvidenceLabel
  reason: string
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
    /*
     * SUPPORTED INFERENCE:
     * 002_000_00001 is currently the strongest opening-tutorial map
     * candidate. A named archived Millennium Tree map produces a strong
     * geometric match against the recovered authentic render, this exact map
     * package exists in the recovered Global cache, and the user-supplied
     * original tutorial frame independently matches the same field family.
     *
     * The exact tutorial Room, spawn, encounter population, and quest-instance
     * state remain unresolved, so mapIdentity stays UNRESOLVED.
     */
    candidatePriority:
      Object.freeze([
        {
          mapId:
            '002_000_00001',
          label:
            'SUPPORTED INFERENCE' as const,
          reason:
            'Named Millennium Tree archive strongly matches the recovered render; the exact package exists in the Global cache and independently matches the original tutorial field family.',
        },
      ] satisfies
        readonly LogresTutorialMapCandidateEvidence[]),
    /*
     * SUPPORTED INFERENCE:
     * 001_000_00001 was previously prioritized by semantic quest-reference
     * evidence. Authentic rendering shows a dense settlement/castle field that
     * does not match the confirmed tutorial recording's grassy cliff/water
     * topology, so it is no longer an active tutorial-map candidate.
     */
    rejectedCandidates:
      Object.freeze([
        {
          mapId:
            '001_000_00001',
          label:
            'SUPPORTED INFERENCE' as const,
          reason:
            'Authentic recovered-map render does not match the original tutorial video terrain topology.',
        },
      ] satisfies
        readonly LogresTutorialMapCandidateEvidence[]),
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
