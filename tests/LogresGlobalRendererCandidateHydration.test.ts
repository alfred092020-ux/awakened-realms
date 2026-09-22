import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

describe(
  'private Global renderer-candidate hydration',
  () => {
    it(
      'passes deterministic synthetic self-test without proprietary files',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/hydrate_global_renderer_candidate.py',
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
          'Logres Global candidate hydrator self-test: PASS',
        )
      },
    )
  },
)
