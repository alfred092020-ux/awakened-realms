import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

describe(
  'private Global tutorial HUD hydration',
  () => {
    it(
      'passes deterministic synthetic self-test without proprietary files',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/hydrate_global_tutorial_hud.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        expect(
          output,
        ).toContain(
          'Logres Global tutorial HUD hydrator self-test: PASS',
        )
      },
    )
  },
)
