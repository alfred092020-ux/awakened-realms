import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TUTORIAL_VIDEO_EVIDENCE,
  logresTutorialStageIds,
} from '../src/game/logres/tutorial/LogresTutorialVideoEvidence'

describe(
  'original tutorial video evidence',
  () => {
    it(
      'keeps tutorial map identity unresolved and removes visually rejected candidates',
      () => {
        expect(
          LOGRES_TUTORIAL_VIDEO_EVIDENCE
            .mapIdentity,
        ).toEqual({
          mapId: null,
          label:
            'UNRESOLVED',
        })

        expect(
          LOGRES_TUTORIAL_VIDEO_EVIDENCE
            .candidatePriority,
        ).toEqual([])

        expect(
          LOGRES_TUTORIAL_VIDEO_EVIDENCE
            .rejectedCandidates,
        ).toContainEqual({
          mapId:
            '001_000_00001',
          label:
            'SUPPORTED INFERENCE',
          reason:
            'Authentic recovered-map render does not match the original tutorial video terrain topology.',
        })
      },
    )

    it(
      'preserves observed tutorial sequence without inventing later stages',
      () => {
        expect(
          logresTutorialStageIds(),
        ).toEqual([
          'npc-first-contact',
          'field-control-visible',
          'quest-start-win-battle',
          'guided-field-encounter',
          'battle-entry',
          'first-attack-guidance',
        ])
      },
    )
  },
)
