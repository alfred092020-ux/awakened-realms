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
      'keeps exact tutorial map identity unresolved while prioritizing the strongest cross-checked candidate',
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
            .candidatePriority[0],
        ).toEqual({
          mapId:
            '002_000_00001',
          label:
            'SUPPORTED INFERENCE',
          reason:
            'Named Millennium Tree archive strongly matches the recovered render; the exact package exists in the Global cache and independently matches the original tutorial field family.',
        })

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
