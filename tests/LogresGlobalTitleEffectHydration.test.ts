import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

describe(
  'private Global title-effect hydration',
  () => {
    it(
      'passes deterministic synthetic self-test without proprietary files',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/hydrate_global_title_effects.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        const result =
          JSON.parse(
            output,
          )

        expect(
          result,
        ).toMatchObject({
          ok:
            true,

          png_size: [
            2,
            3,
          ],
        })
      },
    )
  },
)
