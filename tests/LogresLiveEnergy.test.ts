import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  EnergySystem,
} from '../src/game/combat/EnergySystem'

describe(
  'Logres live EP behavior',
  () => {
    it(
      'starts battle with zero EP',
      () => {
        const energy =
          new EnergySystem(
            100,
            8,
          )

        expect(
          energy.getEnergy(),
        ).toBe(0)
      },
    )

    it(
      'does not regenerate EP passively',
      () => {
        const energy =
          new EnergySystem(
            100,
            8,
          )

        energy.update(60000)

        expect(
          energy.getEnergy(),
        ).toBe(0)
      },
    )

    it(
      'gains EP through attacks',
      () => {
        const energy =
          new EnergySystem(
            100,
            0,
          )

        const gained =
          energy.gainFromAttack(5)

        expect(gained)
          .toBe(5)

        expect(
          energy.getEnergy(),
        ).toBe(5)
      },
    )

    it(
      'spends EP through the weapon battle state',
      () => {
        const energy =
          new EnergySystem(
            100,
            0,
          )

        energy.gainFromAttack(10)

        expect(
          energy.spend(4),
        ).toBe(true)

        expect(
          energy.getEnergy(),
        ).toBe(6)
      },
    )
  },
)
