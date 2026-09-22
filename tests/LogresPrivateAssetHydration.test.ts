import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  execFileSync,
} from 'node:child_process'

import {
  resolve,
} from 'node:path'

describe(
  'Logres private asset hydrator',
  () => {
    it(
      'passes its synthetic MBN / ASTC / KTX self-test',
      () => {
        const script =
          resolve(
            process.cwd(),
            'scripts/logres/hydrate_private_assets.py',
          )

        const output =
          execFileSync(
            'python3',
            [
              script,
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
          'Logres private asset hydrator self-test: PASS',
        )
      },
    )
  },
)
