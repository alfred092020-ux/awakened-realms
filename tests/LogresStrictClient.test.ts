import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_CLIENT_FACTS,
} from '../src/game/logres/generated/ExtractedClientFacts'

import {
  LOGRES_ASSETS,
} from '../src/game/logres/ui/LogresRuntimeAssets'

describe(
  'strict Logres client reconstruction',
  () => {
    it(
      'uses extracted EP behavior',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .battle
            .epRecoversByAttack,
        ).toBe(true)
      },
    )

    it(
      'uses extracted weapon-switch gesture',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .battle
            .weaponSwitchGesture,
        ).toBe('slide')
      },
    )

    it(
      'uses extracted normal skill slot count',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .equipment
            .normalSkillSlots,
        ).toBe(3)
      },
    )

    it(
      'uses extracted field scale',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .field
            .initialViewScale,
        ).toBe(1.25)
      },
    )

    it(
      'loads only extracted client visual paths',
      () => {
        for (
          const asset of
          Object.values(
            LOGRES_ASSETS,
          )
        ) {
          expect(
            asset.url,
          ).toContain(
            '/__logres_ref/japanese/',
          )
        }
      },
    )
  },
)
