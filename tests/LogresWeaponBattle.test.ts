import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  MAX_ACTIVE_WEAPONS,
  WeaponBattleState,
} from '../src/game/logres/battle/WeaponBattleState'

const weapons = [
  {
    itemId: 'weapon-1',
    skillId: 'skill-1',
  },
  {
    itemId: 'weapon-2',
    skillId: 'skill-2',
  },
  {
    itemId: 'weapon-3',
    skillId: 'skill-3',
  },
]

describe(
  'Logres weapon battle state',
  () => {
    it(
      'supports weapon switching',
      () => {
        const battle =
          new WeaponBattleState(
            weapons,
          )

        expect(
          battle.switchWeapon(2),
        ).toBe(true)

        expect(
          battle.getActiveWeapon()
            ?.itemId,
        ).toBe('weapon-3')
      },
    )

    it(
      'gains EP from attacks',
      () => {
        const battle =
          new WeaponBattleState(
            weapons,
          )

        battle.gainEp(3)
        battle.gainEp(2)

        expect(
          battle.getSnapshot().ep,
        ).toBe(5)
      },
    )

    it(
      'spends EP for skills',
      () => {
        const battle =
          new WeaponBattleState(
            weapons,
          )

        battle.gainEp(5)

        expect(
          battle.spendEp(3),
        ).toBe(true)

        expect(
          battle.getSnapshot().ep,
        ).toBe(2)
      },
    )

    it(
      'rejects more than five active weapons',
      () => {
        expect(
          () =>
            new WeaponBattleState(
              Array.from(
                {
                  length:
                    MAX_ACTIVE_WEAPONS +
                    1,
                },
                (_, index) => ({
                  itemId:
                    `weapon-${index}`,
                  skillId:
                    `skill-${index}`,
                }),
              ),
            ),
        ).toThrow()
      },
    )
  },
)
