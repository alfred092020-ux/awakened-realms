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
      'keeps tutorial map identity unresolved while retaining the strongest current candidate',
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
        ).toMatchObject({
          mapId:
            '001_000_00001',
          label:
            'SUPPORTED INFERENCE',
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
