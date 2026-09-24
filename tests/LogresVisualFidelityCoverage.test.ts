import {
  execFileSync,
  spawnSync,
} from 'node:child_process'
import {
  mkdtempSync,
  readFileSync,
  rmSync,
} from 'node:fs'
import {
  tmpdir,
} from 'node:os'
import path from 'node:path'
import {
  describe,
  expect,
  it,
} from 'vitest'

const visualTruth =
  path.resolve(
    'ops/logres-control-plane/bin/logres-visual-truth',
  )
const visualE2e =
  path.resolve(
    'e2e/logres-visual-checkpoints.spec.mjs',
  )

const required = [
  'title',
  'onboarding',
  'field',
  'npc',
  'battle',
  'victory',
  'menu',
] as const

function tempVisualTruthEnv() {
  const root =
    mkdtempSync(
      path.join(
        tmpdir(),
        'logres-visual-fidelity-',
      ),
    )

  return {
    root,
    env: {
      ...process.env,
      LOGRES_CONTROL_DB:
        path.join(
          root,
          'control.sqlite',
        ),
      LOGRES_VISUAL_TRUTH_SPOOL_DIR:
        path.join(
          root,
          'spool',
        ),
    },
  }
}

describe(
  'Logres visual fidelity coverage',
  () => {
    it(
      'declares all required fidelity checkpoints in the canonical E2E gate',
      () => {
        const source =
          readFileSync(
            visualE2e,
            'utf8',
          )

        for (
          const checkpoint of
          required
        ) {
          expect(source)
            .toContain(
              `'${checkpoint}'`,
            )
        }

        expect(source)
          .toContain(
            'REQUIRED_VISUAL_CHECKPOINTS',
          )
        expect(source)
          .toContain(
            "'REVIEW'",
          )
        expect(source)
          .toContain(
            "reference_status: 'MISSING'",
          )
      },
    )

    it(
      'refuses PASS without both a reference artifact and measurement metrics',
      () => {
        const {
          root,
          env,
        } =
          tempVisualTruthEnv()

        try {
          execFileSync(
            visualTruth,
            [
              'init',
            ],
            {
              env,
              encoding:
                'utf8',
            },
          )

          const sha =
            'a'.repeat(40)

          const missingReference =
            spawnSync(
              visualTruth,
              [
                'record',
                sha,
                'title',
                '/tmp/observed.png',
                'PASS',
                '--metrics',
                '{"rmse":0}',
              ],
              {
                env,
                encoding:
                  'utf8',
              },
            )

          expect(
            missingReference.status,
          ).not.toBe(0)
          expect(
            missingReference.stderr,
          ).toContain(
            'PASS requires explicit reference artifact and measurement metrics',
          )

          const missingMetrics =
            spawnSync(
              visualTruth,
              [
                'record',
                sha,
                'title',
                '/tmp/observed.png',
                'PASS',
                '--reference',
                '/tmp/reference.png',
              ],
              {
                env,
                encoding:
                  'utf8',
              },
            )

          expect(
            missingMetrics.status,
          ).not.toBe(0)

          const accepted =
            JSON.parse(
              execFileSync(
                visualTruth,
                [
                  'record',
                  sha,
                  'title',
                  '/tmp/observed.png',
                  'PASS',
                  '--reference',
                  '/tmp/reference.png',
                  '--metrics',
                  '{"rmse":0,"changed_pixel_ratio":0}',
                ],
                {
                  env,
                  encoding:
                    'utf8',
                },
              ),
            )

          expect(
            accepted.spooled,
          ).toBe(false)
        } finally {
          rmSync(
            root,
            {
              recursive: true,
              force: true,
            },
          )
        }
      },
    )

    it(
      'accepts missing-reference coverage only as REVIEW',
      () => {
        const {
          root,
          env,
        } =
          tempVisualTruthEnv()

        try {
          execFileSync(
            visualTruth,
            [
              'init',
            ],
            {
              env,
              encoding:
                'utf8',
            },
          )

          const sha =
            'b'.repeat(40)

          execFileSync(
            visualTruth,
            [
              'record',
              sha,
              'npc',
              '/tmp/npc.png',
              'REVIEW',
              '--metrics',
              '{"reference_status":"MISSING","measurement":"SCREENSHOT_CAPTURE"}',
            ],
            {
              env,
              encoding:
                'utf8',
            },
          )

          const latest =
            JSON.parse(
              execFileSync(
                visualTruth,
                [
                  'latest',
                  'npc',
                ],
                {
                  env,
                  encoding:
                    'utf8',
                },
              ),
            )

          expect(
            latest.sha,
          ).toBe(sha)
          expect(
            latest.verdict,
          ).toBe(
            'REVIEW',
          )
          expect(
            latest.reference_artifact,
          ).toBeNull()
          expect(
            latest.metrics,
          ).toMatchObject({
            reference_status:
              'MISSING',
            measurement:
              'SCREENSHOT_CAPTURE',
          })
        } finally {
          rmSync(
            root,
            {
              recursive: true,
              force: true,
            },
          )
        }
      },
    )
  },
)
