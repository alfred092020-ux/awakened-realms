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
  'Logres private map terminal record inspector',
  () => {
    it(
      'profiles synthetic opaque protobuf records without semantic guessing',
      () => {
        const script =
          resolve(
            process.cwd(),
            'scripts/logres/inspect_private_map_records.py',
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
          'Logres private map terminal record inspector self-test: PASS',
        )
      },
    )
  },
)
