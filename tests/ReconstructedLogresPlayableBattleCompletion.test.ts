import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  completeReconstructedPlayableBattle,
  LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_FIELD_NAME,
  LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_MOVEMENT_STATE,
  LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY,
  LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
} from '../src/game/logres/battle/ReconstructedLogresPlayableBattleCompletion'

describe(
  'reconstructed playable battle completion',
  () => {
    it(
      'returns a deterministic reconstructed result, reward, and field handoff',
      () => {
        const result =
          completeReconstructedPlayableBattle({
            battleSystemRef:
              'battle-system-1',
            resultRef:
              'result-1',
            rawOutcomeCode:
              0,
            inventoryProjectionRef:
              'projection-1',
          })

        expect(
          result.flow,
        ).toMatchObject({
          battleSystemRef:
            'battle-system-1',
          phase:
            'field-return-ready',
          result: {
            resultRef:
              'result-1',
            rawOutcomeCode:
              0,
          },
          reward: {
            inventoryProjectionRef:
              'projection-1',
          },
        })

        expect(
          result.rewardApplied,
        ).toBe(
          true,
        )

        expect(
          result.inventory.entries,
        ).toEqual([
          expect.objectContaining({
            itemKey:
              LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
            grantKey:
              LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
          }),
        ])

        expect(
          result.fieldReturn,
        ).toEqual({
          sceneKey:
            LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_SCENE_KEY,
          fieldName:
            LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_FIELD_NAME,
          movementState:
            LOGRES_PLAYABLE_BATTLE_FIELD_RETURN_MOVEMENT_STATE,
        })
      },
    )

    it(
      'keeps the reconstructed reward grant idempotent across repeated completion authority calls',
      () => {
        const first =
          completeReconstructedPlayableBattle()

        const retry =
          completeReconstructedPlayableBattle({
            inventory:
              first.inventory,
          })

        expect(
          retry.rewardApplied,
        ).toBe(
          false,
        )

        expect(
          retry.inventory,
        ).toBe(
          first.inventory,
        )
      },
    )
  },
)
