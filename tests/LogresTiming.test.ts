import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  logresDevMs,
} from '../src/game/logres/LogresDevSettings'

describe(
  'strict Logres timing',
  () => {
    it(
      'preserves recovered client timing values at runtime',
      () => {
        expect(
          logresDevMs(
            1500,
          ),
        ).toBe(
          1500,
        )

        expect(
          logresDevMs(
            300,
          ),
        ).toBe(
          300,
        )
      },
    )
  },
)
