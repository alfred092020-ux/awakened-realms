import {
  readFileSync,
} from 'node:fs'

import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  completeReconstructedLogresPlayableBattle,
  LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
  LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
} from '../src/game/logres/battle/ReconstructedLogresPlayableBattleLoop'

import {
  LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
  LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY,
  ReconstructedLogresPlayableBattleAuthority,
} from '../src/game/logres/replacement-server/ReconstructedLogresPlayableBattleAuthority'

function normalAttack(
  commandId: string,
) {
  return {
    commandId,
    command: {
      type:
        'normal-attack' as const,
      weaponSlot:
        0,
      weaponRef:
        'reconstructed-tutorial-weapon',
      skillRef:
        'reconstructed-normal-attack',
    },
  }
}

describe(
  'playable reconstructed battle resolution',
  () => {
    it(
      'reaches reconstructed victory after three distinct accepted playable commands',
      () => {
        const authority =
          new ReconstructedLogresPlayableBattleAuthority()

        expect(
          authority.submitCommand(
            normalAttack(
              'command-1',
            ),
          ).outcome,
        ).toBe(
          'continue',
        )

        expect(
          authority.submitCommand(
            normalAttack(
              'command-2',
            ),
          ).outcome,
        ).toBe(
          'continue',
        )

        const victory =
          authority.submitCommand(
            normalAttack(
              'command-3',
            ),
          )

        expect(
          victory.outcome,
        ).toBe(
          'victory',
        )

        expect(
          victory.snapshot,
        ).toMatchObject({
          provenance:
            LOGRES_PLAYABLE_BATTLE_AUTHORITY_PROVENANCE,
          phase:
            'victory-ready',
          acceptedCommandCount:
            LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY,
          victoryThreshold:
            LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY,
          historicalDamageFormulaRecovered:
            false,
          historicalEnemyHpRecovered:
            false,
          resultAuthority:
            'RECONSTRUCTED',
        })
      },
    )

    it(
      'treats a repeated command id as an idempotent delivery retry',
      () => {
        const authority =
          new ReconstructedLogresPlayableBattleAuthority()

        const first =
          authority.submitCommand(
            normalAttack(
              'same-command',
            ),
          )

        const duplicate =
          authority.submitCommand(
            normalAttack(
              'same-command',
            ),
          )

        expect(
          first.duplicate,
        ).toBe(
          false,
        )

        expect(
          duplicate.duplicate,
        ).toBe(
          true,
        )

        expect(
          duplicate.snapshot
            .acceptedCommandCount,
        ).toBe(
          1,
        )

        authority.submitCommand(
          normalAttack(
            'command-2',
          ),
        )

        expect(
          authority.submitCommand(
            normalAttack(
              'command-3',
            ),
          ).outcome,
        ).toBe(
          'victory',
        )
      },
    )

    it(
      'rejects a new command after reconstructed victory while preserving duplicate retry',
      () => {
        const authority =
          new ReconstructedLogresPlayableBattleAuthority()

        for (
          let index = 1;
          index <=
          LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY;
          index += 1
        ) {
          authority.submitCommand(
            normalAttack(
              `command-${index}`,
            ),
          )
        }

        expect(
          authority.submitCommand(
            normalAttack(
              'command-3',
            ),
          ),
        ).toMatchObject({
          duplicate:
            true,
          outcome:
            'victory',
        })

        expect(
          () =>
            authority.submitCommand(
              normalAttack(
                'command-4',
              ),
            ),
        ).toThrow(
          'already resolved',
        )
      },
    )

    it(
      'completes victory -> reconstructed reward -> inventory -> field-return-ready',
      () => {
        const result =
          completeReconstructedLogresPlayableBattle()

        expect(
          result.flow.phase,
        ).toBe(
          'field-return-ready',
        )

        expect(
          result.rewardApplied,
        ).toBe(
          true,
        )

        expect(
          result.inventory.revision,
        ).toBe(
          1,
        )

        expect(
          result.inventory.entries,
        ).toEqual([
          expect.objectContaining({
            itemKey:
              LOGRES_PLAYABLE_BATTLE_REWARD_ITEM_KEY,
            originalItemId:
              null,
            quantity:
              1,
            grantKey:
              LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
          }),
        ])
      },
    )

    it(
      'prevents duplicate playable reward delivery across repeated completion attempts',
      () => {
        const first =
          completeReconstructedLogresPlayableBattle()

        const retry =
          completeReconstructedLogresPlayableBattle(
            first.inventory,
          )

        expect(
          retry.rewardApplied,
        ).toBe(
          false,
        )

        expect(
          retry.inventory.revision,
        ).toBe(
          1,
        )

        expect(
          retry.inventory.entries,
        ).toHaveLength(
          1,
        )
      },
    )

    it(
      'models the whole playable authority path without hidden harness state',
      () => {
        const authority =
          new ReconstructedLogresPlayableBattleAuthority()

        let outcome:
          | 'continue'
          | 'victory' =
            'continue'

        for (
          let index = 1;
          index <=
          LOGRES_PLAYABLE_BATTLE_COMMANDS_TO_VICTORY;
          index += 1
        ) {
          outcome =
            authority
              .submitCommand(
                normalAttack(
                  `tap-${index}`,
                ),
              )
              .outcome
        }

        expect(
          outcome,
        ).toBe(
          'victory',
        )

        const completion =
          completeReconstructedLogresPlayableBattle()

        expect(
          completion.flow.phase,
        ).toBe(
          'field-return-ready',
        )

        expect(
          completion.inventory.appliedGrantKeys,
        ).toEqual([
          LOGRES_PLAYABLE_BATTLE_GRANT_KEY,
        ])
      },
    )

    it(
      'wires normal enemy taps through playable authority and back to the field scene',
      () => {
        const source =
          readFileSync(
            'src/game/scenes/LogresBattleScene.ts',
            'utf8',
          )

        expect(
          source,
        ).toContain(
          "'logres-request-normal-attack'",
        )

        expect(
          source,
        ).toContain(
          'handlePlayableBattleCommand',
        )

        expect(
          source,
        ).toContain(
          'completeReconstructedLogresPlayableBattle',
        )

        expect(
          source,
        ).toContain(
          "'logres.playableBattle.status'",
        )

        expect(
          source,
        ).toContain(
          "'LogresFieldScene'",
        )

        expect(
          source,
        ).toContain(
          'TAP ENEMY TO ATTACK',
        )
      },
    )
  },
)
