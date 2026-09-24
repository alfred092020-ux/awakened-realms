import {
  readFileSync,
} from 'node:fs'
import {
  resolve,
} from 'node:path'
import {
  describe,
  expect,
  it,
} from 'vitest'

type BudgetProfile = {
  exact_sha_required: boolean
  budgets: Record<string, number>
}

type Measurement = {
  sha: string
  metrics: Record<string, number | null | undefined>
}

const config = JSON.parse(
  readFileSync(
    resolve(
      'ops/logres-control-plane/config/performance_budgets.json',
    ),
    'utf8',
  ),
)

function metricName(
  budgetName: string,
) {
  if (!budgetName.endsWith('_max')) {
    throw new Error(
      `Unsupported performance budget key: ${budgetName}`,
    )
  }

  return budgetName.slice(
    0,
    -4,
  )
}

function evaluatePerformanceMeasurement(
  profile: BudgetProfile,
  measurement: Measurement,
  expectedSha: string,
) {
  const failures: string[] =
    []

  if (
    profile.exact_sha_required
  ) {
    if (
      !/^[0-9a-f]{40}$/.test(
        expectedSha,
      )
    ) {
      failures.push(
        'expected SHA is not exact',
      )
    }

    if (
      measurement.sha !==
      expectedSha
    ) {
      failures.push(
        `measurement SHA mismatch: ${measurement.sha} != ${expectedSha}`,
      )
    }
  }

  for (
    const [
      budgetName,
      max,
    ]
    of Object.entries(
      profile.budgets,
    )
  ) {
    const metric =
      metricName(
        budgetName,
      )

    const value =
      measurement.metrics[
        metric
      ]

    if (
      typeof value !==
        'number' ||
      !Number.isFinite(
        value,
      )
    ) {
      failures.push(
        `missing required metric: ${metric}`,
      )

      continue
    }

    if (value > max) {
      failures.push(
        `${metric} ${value} exceeds max ${max}`,
      )
    }
  }

  return failures
}

describe(
  'Logres performance budget contract',
  () => {
    it(
      'keeps historical Global performance explicitly unresolved',
      () => {
        expect(
          config.schema,
        ).toBe(
          'logres-performance-budgets-v1',
        )

        expect(
          config
            .historical_global_performance,
        ).toMatchObject({
          status:
            'UNRESOLVED',
        })
      },
    )

    it(
      'locks the three-sample Chromium calibration to one exact SHA inside budget',
      () => {
        const chromium =
          config.runtime_classes
            .chromium_ci_720x1280

        expect(
          chromium
            .calibration
            .sha,
        ).toMatch(
          /^[0-9a-f]{40}$/,
        )

        expect(
          chromium
            .calibration
            .samples,
        ).toBe(
          3,
        )

        const metrics =
          [
            'bootstrap_ms',
            'field_ready_ms',
            'frame_p95_ms',
            'frame_p99_ms',
            'used_js_heap_mb',
          ]

        for (
          const metric
          of metrics
        ) {
          const max =
            chromium
              .budgets[
                `${metric}_max`
              ]

          const samples =
            chromium
              .calibration[
                metric
              ]

          expect(
            samples,
          ).toHaveLength(
            3,
          )

          for (
            const value
            of samples
          ) {
            expect(
              value,
              `${metric} calibration sample must remain within budget`,
            ).toBeLessThanOrEqual(
              max,
            )
          }
        }
      },
    )

    it(
      'accepts the measured Samsung baseline with explicit headroom',
      () => {
        const samsung =
          config.runtime_classes
            .samsung_s25_ultra_android16

        const baseline =
          samsung.baseline

        const failures =
          evaluatePerformanceMeasurement(
            {
              exact_sha_required:
                samsung.exact_sha_required,
              budgets:
                samsung.budgets,
            },
            {
              sha:
                baseline.sha,
              metrics: {
                cold_start_ms:
                  baseline.cold_start_ms,
                frame_p95_ms:
                  baseline.frame_p95_ms,
                frame_p99_ms:
                  baseline.frame_p99_ms,
                jank_percent:
                  baseline.jank_percent,
                rss_mb:
                  baseline.rss_mb,
              },
            },
            baseline.sha,
          )

        expect(
          failures,
        ).toEqual([])
      },
    )

    it(
      'fails closed on a measurement from another SHA',
      () => {
        const profile =
          config.runtime_classes
            .chromium_ci_720x1280

        const failures =
          evaluatePerformanceMeasurement(
            profile,
            {
              sha:
                'b'.repeat(
                  40,
                ),
              metrics: {
                bootstrap_ms:
                  100,
                field_ready_ms:
                  100,
                frame_p95_ms:
                  16,
                frame_p99_ms:
                  17,
                used_js_heap_mb:
                  50,
              },
            },
            'a'.repeat(
              40,
            ),
          )

        expect(
          failures.join(
            '\n',
          ),
        ).toContain(
          'measurement SHA mismatch',
        )
      },
    )

    it(
      'fails closed when a required metric is missing',
      () => {
        const profile =
          config.runtime_classes
            .chromium_ci_720x1280

        const sha =
          'a'.repeat(
            40,
          )

        const failures =
          evaluatePerformanceMeasurement(
            profile,
            {
              sha,
              metrics: {
                bootstrap_ms:
                  100,
                field_ready_ms:
                  100,
                frame_p95_ms:
                  16,
                frame_p99_ms:
                  17,
              },
            },
            sha,
          )

        expect(
          failures,
        ).toContain(
          'missing required metric: used_js_heap_mb',
        )
      },
    )

    it(
      'fails closed when any budget is exceeded',
      () => {
        const profile =
          config.runtime_classes
            .chromium_ci_720x1280

        const sha =
          'a'.repeat(
            40,
          )

        const failures =
          evaluatePerformanceMeasurement(
            profile,
            {
              sha,
              metrics: {
                bootstrap_ms:
                  profile
                    .budgets
                    .bootstrap_ms_max +
                  1,
                field_ready_ms:
                  100,
                frame_p95_ms:
                  16,
                frame_p99_ms:
                  17,
                used_js_heap_mb:
                  50,
              },
            },
            sha,
          )

        expect(
          failures.join(
            '\n',
          ),
        ).toContain(
          'bootstrap_ms',
        )
      },
    )

    it(
      'does not use noisy short-run CPU as a Samsung release budget',
      () => {
        const samsung =
          config.runtime_classes
            .samsung_s25_ultra_android16

        expect(
          samsung
            .budgets
            .cpu_percent_max,
        ).toBeUndefined()

        expect(
          samsung.notes.join(
            ' ',
          ),
        ).toContain(
          'too noisy',
        )
      },
    )
  },
)
