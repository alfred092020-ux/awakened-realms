import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

describe(
  'Global 3.0.24 bootstrap asset catalog validator',
  () => {
    it(
      'validates synthetic metadata without requiring private asset bytes',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/summarize_global3024_bootstrap_assets.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        expect(
          JSON.parse(
            output,
          ),
        ).toEqual({
          audio:
            0,

          members:
            6,

          ok:
            true,

          packages:
            2,
        })
      },
    )
  },
)
