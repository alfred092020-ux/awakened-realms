import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_UI_ASSETS,
} from '../src/game/logres/ui/LogresRuntimeAssets'

describe(
  'Logres runtime visual bridge',
  () => {
    it(
      'provides five extracted weapon frames',
      () => {
        expect(
          LOGRES_UI_ASSETS
            .weaponFrames,
        ).toHaveLength(5)
      },
    )

    it(
      'provides extracted skill UI bases',
      () => {
        expect(
          LOGRES_UI_ASSETS
            .skillBase,
        ).toBe(
          'logres-ui-skill-base',
        )

        expect(
          LOGRES_UI_ASSETS
            .equipmentSkillBase,
        ).toBe(
          'logres-ui-equipment-skill-base',
        )
      },
    )
  },
)
