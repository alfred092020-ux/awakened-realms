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
  'Logres public field navigation inspector',
  () => {
    it(
      'keeps the native navigation scan bounded to the explicit allowlist',
      () => {
        const script =
          resolve(
            process.cwd(),
            'scripts/logres/inspect_public_field_navigation.py',
          )

        const output =
          execFileSync(
            'python3',
            [
              '-B',
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
          'Logres public field navigation inspector self-test: PASS',
        )
      },
    )
  },
)
