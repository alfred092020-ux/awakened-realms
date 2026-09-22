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

function runPythonSelfTest(
  scriptName: string,
) {
  const script =
    resolve(
      process.cwd(),
      'scripts/logres',
      scriptName,
    )

  return execFileSync(
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
}

describe(
  'Logres private extraction tooling',
  () => {
    it(
      'passes the MBN / ASTC / KTX hydrator self-test',
      () => {
        expect(
          runPythonSelfTest(
            'hydrate_private_assets.py',
          ),
        ).toContain(
          'Logres private asset hydrator self-test: PASS',
        )
      },
    )

    it(
      'passes the raw map protobuf-wire inspector self-test',
      () => {
        expect(
          runPythonSelfTest(
            'inspect_private_map_packages.py',
          ),
        ).toContain(
          'Logres private map package inspector self-test: PASS',
        )
      },
    )
  },
)
