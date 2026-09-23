import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_RECONSTRUCTED_BATTLE_RESOLUTION_PROVENANCE,
  ReconstructedLogresBattleResolutionFlow,
} from '../src/game/logres/battle/ReconstructedLogresBattleResolutionFlow'

describe(
  'reconstructed Logres battle resolution flow',
  () => {
    it(
      'keeps result, reward, and field overlay as distinct stages',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            'battle-system-1',
          )

        flow.recordResult({
          resultRef:
            null,
          rawOutcomeCode:
            0,
        })

        expect(
          flow.snapshot(),
        ).toMatchObject({
          provenance:
            LOGRES_RECONSTRUCTED_BATTLE_RESOLUTION_PROVENANCE,
          phase:
            'result-received',
          reward:
            null,
          fieldOverlay:
            null,
        })

        flow.markResultPresented()

        flow.recordRewardStage({
          rewardKey:
            'tutorial-reward',
          originalRewardRef:
            null,
          inventoryProjectionRef:
            null,
        })

        expect(
          flow.snapshot()
            .phase,
        ).toBe(
          'reward-ready',
        )

        flow.markRewardPresented()
        flow.markFieldReturnReady()

        const overlay =
          flow.queueFieldOverlay({
            overlayKey:
              'quest-cleared',
            originalQuestRef:
              null,
          })

        expect(
          overlay,
        ).toEqual({
          overlayKey:
            'quest-cleared',
          originalQuestRef:
            null,
        })
      },
    )

    it(
      'never interprets an unresolved raw battle outcome code',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        flow.recordResult({
          resultRef:
            null,
          rawOutcomeCode:
            99,
        })

        expect(
          flow.snapshot()
            .result,
        ).toEqual({
          resultRef:
            null,
          rawOutcomeCode:
            99,
        })
      },
    )

    it(
      'requires result presentation before reward becomes available',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        flow.recordResult({
          resultRef:
            null,
          rawOutcomeCode:
            null,
        })

        expect(
          () =>
            flow.recordRewardStage({
              rewardKey:
                null,
              originalRewardRef:
                null,
              inventoryProjectionRef:
                null,
            }),
        ).toThrow(
          'separate from battle result presentation',
        )
      },
    )

    it(
      'permits an explicit no-known-reward stage without inventing reward data',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        flow.recordResult({
          resultRef:
            null,
          rawOutcomeCode:
            null,
        })

        flow.markResultPresented()

        flow.recordRewardStage({
          rewardKey:
            null,
          originalRewardRef:
            null,
          inventoryProjectionRef:
            null,
        })

        expect(
          flow.snapshot()
            .reward,
        ).toEqual({
          rewardKey:
            null,
          originalRewardRef:
            null,
          inventoryProjectionRef:
            null,
        })
      },
    )

    it(
      'does not queue a quest-clear overlay automatically after battle',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        flow.recordResult({
          resultRef:
            null,
          rawOutcomeCode:
            null,
        })

        flow.markResultPresented()

        flow.recordRewardStage({
          rewardKey:
            null,
          originalRewardRef:
            null,
          inventoryProjectionRef:
            null,
        })

        flow.markRewardPresented()
        flow.markFieldReturnReady()

        expect(
          flow.snapshot()
            .fieldOverlay,
        ).toBeNull()
      },
    )

    it(
      'rejects field overlay before field-return stage',
      () => {
        const flow =
          new ReconstructedLogresBattleResolutionFlow(
            null,
          )

        expect(
          () =>
            flow.queueFieldOverlay({
              overlayKey:
                'quest-cleared',
              originalQuestRef:
                null,
            }),
        ).toThrow(
          'only be queued after return-to-field',
        )
      },
    )
  },
)
