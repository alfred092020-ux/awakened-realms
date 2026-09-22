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
  'Logres Oracle worker',
  () => {
    it(
      'rejects unsafe manifests and paths in its synthetic self-test',
      () => {
        const script =
          resolve(
            process.cwd(),
            'scripts/logres/oracle_worker.py',
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
          'Logres Oracle worker self-test: PASS',
        )
      },
    )
  },
)
