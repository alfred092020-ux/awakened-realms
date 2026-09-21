import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_CLIENT_FACTS,
} from '../src/game/logres/generated/ExtractedClientFacts'

describe(
  'Logres extracted command layout',
  () => {
    it(
      'uses three normal command skill slots',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .equipment
            .normalSkillSlots,
        ).toBe(3)
      },
    )

    it(
      'uses slide as the extracted weapon switch gesture',
      () => {
        expect(
          LOGRES_CLIENT_FACTS
            .battle
            .weaponSwitchGesture,
        ).toBe('slide')
      },
    )
  },
)
