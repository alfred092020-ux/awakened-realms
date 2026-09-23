import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

describe(
  'Logres title LFLA inspector',
  () => {
    it(
      'flattens nested protobuf-wire transforms deterministically',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/flatten_title_lfla.py',
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

          width:
            720,

          height:
            1280,

          leaf: {
            ref:
              'png/test.png',

            x:
              80,

            y:
              160,

            scale_x:
              2,

            scale_y:
              2,
          },
        })
      },
    )
  },
)
