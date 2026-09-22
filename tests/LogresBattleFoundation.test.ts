import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  getLogresBattleFoundation,
  logresNormalSkillSlotIndices,
} from '../src/game/logres/battle/LogresBattleFoundation'

describe(
  'Logres battle foundation',
  () => {
    it(
      'exposes only confirmed extracted client facts',
      () => {
        expect(
          getLogresBattleFoundation(),
        ).toEqual({
          normalSkillSlots: 3,
          weaponSwitchGesture:
            'slide',
          epRecoversByAttack:
            true,
          epAnimation:
            true,
          skillViewDefaultOffset:
            [0, 285],
          commandSkillNameOffset:
            [0, -129],
        })
      },
    )

    it(
      'produces the confirmed normal skill slot indices',
      () => {
        expect(
          logresNormalSkillSlotIndices(),
        ).toEqual([
          0,
          1,
          2,
        ])
      },
    )
  },
)
