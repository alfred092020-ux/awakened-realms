import {
  execFileSync,
} from 'node:child_process'
import {
  mkdir,
  readFile,
  writeFile,
} from 'node:fs/promises'
import path from 'node:path'

import {
  expect,
  test,
} from '@playwright/test'

function exactSha() {
  const fromEnv =
    String(
      process.env
        .LOGRES_VERIFY_SHA ??
        '',
    ).trim()

  const sha =
    fromEnv ||
    execFileSync(
      'git',
      [
        'rev-parse',
        'HEAD',
      ],
      {
        encoding:
          'utf8',
      },
    ).trim()

  if (
    !/^[0-9a-f]{40}$/.test(
      sha,
    )
  ) {
    throw new Error(
      `Performance gate requires exact lowercase SHA, got: ${sha}`,
    )
  }

  return sha
}

function percentile(
  values,
  percentileValue,
) {
  if (!values.length) {
    throw new Error(
      'No frame samples were captured.',
    )
  }

  const sorted =
    [...values].sort(
      (
        left,
        right,
      ) =>
        left -
        right,
    )

  const index =
    Math.min(
      sorted.length -
        1,
      Math.max(
        0,
        Math.ceil(
          (
            percentileValue /
            100
          ) *
            sorted.length,
        ) -
          1,
      ),
    )

  return sorted[
    index
  ]
}

function budgetFailure(
  metric,
  value,
  max,
) {
  if (
    typeof value !==
      'number' ||
    !Number.isFinite(
      value,
    )
  ) {
    return `Required performance metric missing: ${metric}`
  }

  if (value > max) {
    return `${metric} ${value} exceeds max ${max}`
  }

  return null
}

test(
  'hydrated reconstructed field stays within exact-SHA Chromium performance budgets',
  async ({
    page,
    request,
  }, testInfo) => {
    const config =
      JSON.parse(
        await readFile(
          path.resolve(
            'ops/logres-control-plane/config/performance_budgets.json',
          ),
          'utf8',
        ),
      )

    const profile =
      config
        .runtime_classes
        .chromium_ci_720x1280

    const sha =
      exactSha()

    const candidate =
      await request.get(
        '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
      )

    const contentType =
      candidate.headers()[
        'content-type'
      ] ??
      ''

    if (
      !candidate.ok() ||
      !contentType.includes(
        'application/octet-stream',
      )
    ) {
      throw new Error(
        `Required hydrated field runtime missing: status=${candidate.status()} type=${contentType}`,
      )
    }

    const bootstrapStarted =
      performance.now()

    await page.goto('/')

    await page.waitForFunction(
      () =>
        Boolean(
          window
            .__AWAKENED_REALMS_GAME__
            ?.scene,
        ),
      undefined,
      {
        timeout:
          profile
            .budgets
            .bootstrap_ms_max,
      },
    )

    const bootstrapMs =
      performance.now() -
      bootstrapStarted

    const fieldStarted =
      performance.now()

    await page.evaluate(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__

        game.registry.set(
          'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
          [
            0,
            'Novice',
            0,
            1,
            1,
            1,
            1,
            1,
          ],
        )

        game.scene.start(
          'LogresFieldScene',
        )
      },
    )

    await page.waitForFunction(
      () =>
        window
          .__AWAKENED_REALMS_GAME__
          .registry
          .get(
            'logres.playableField.status',
          ) ===
        'READY',
      undefined,
      {
        timeout:
          profile
            .budgets
            .field_ready_ms_max,
      },
    )

    const fieldReadyMs =
      performance.now() -
      fieldStarted

    const frameIntervals =
      await page.evaluate(
        () =>
          new Promise(
            resolve => {
              const values =
                []

              let previous =
                performance.now()

              let seen =
                0

              const sample =
                now => {
                  const delta =
                    now -
                    previous

                  previous =
                    now

                  seen +=
                    1

                  if (
                    seen >
                    5
                  ) {
                    values.push(
                      delta,
                    )
                  }

                  if (
                    values.length >=
                    120
                  ) {
                    resolve(
                      values,
                    )

                    return
                  }

                  requestAnimationFrame(
                    sample,
                  )
                }

              requestAnimationFrame(
                sample,
              )
            },
          ),
      )

    const frameP95Ms =
      percentile(
        frameIntervals,
        95,
      )

    const frameP99Ms =
      percentile(
        frameIntervals,
        99,
      )

    const usedJsHeapMb =
      await page.evaluate(
        () => {
          const memory =
            performance
              .memory

          if (
            !memory ||
            typeof memory
              .usedJSHeapSize !==
              'number'
          ) {
            return null
          }

          return (
            memory
              .usedJSHeapSize /
            (
              1024 *
              1024
            )
          )
        },
      )

    const metrics = {
      bootstrap_ms:
        Number(
          bootstrapMs.toFixed(
            2,
          ),
        ),
      field_ready_ms:
        Number(
          fieldReadyMs.toFixed(
            2,
          ),
        ),
      frame_p95_ms:
        Number(
          frameP95Ms.toFixed(
            2,
          ),
        ),
      frame_p99_ms:
        Number(
          frameP99Ms.toFixed(
            2,
          ),
        ),
      used_js_heap_mb:
        usedJsHeapMb ===
        null
          ? null
          : Number(
              usedJsHeapMb.toFixed(
                2,
              ),
            ),
    }

    const budgets =
      profile.budgets

    const failures =
      [
        budgetFailure(
          'bootstrap_ms',
          metrics
            .bootstrap_ms,
          budgets
            .bootstrap_ms_max,
        ),
        budgetFailure(
          'field_ready_ms',
          metrics
            .field_ready_ms,
          budgets
            .field_ready_ms_max,
        ),
        budgetFailure(
          'frame_p95_ms',
          metrics
            .frame_p95_ms,
          budgets
            .frame_p95_ms_max,
        ),
        budgetFailure(
          'frame_p99_ms',
          metrics
            .frame_p99_ms,
          budgets
            .frame_p99_ms_max,
        ),
        budgetFailure(
          'used_js_heap_mb',
          metrics
            .used_js_heap_mb,
          budgets
            .used_js_heap_mb_max,
        ),
      ].filter(
        Boolean,
      )

    const artifact = {
      schema:
        'logres-performance-measurement-v1',
      sha,
      runtime_class:
        'chromium_ci_720x1280',
      viewport: {
        width:
          720,
        height:
          1280,
      },
      budgets,
      metrics,
      frame_samples:
        frameIntervals.length,
      fidelity_guards: {
        private_field_runtime_required:
          true,
        visual_checks_disabled:
          false,
        behavioral_checks_disabled:
          false,
        collision_checks_disabled:
          false,
        battle_checks_disabled:
          false,
        content_checks_disabled:
          false,
      },
      historical_global_performance:
        'UNRESOLVED',
      verdict:
        failures.length ===
        0
          ? 'PASS'
          : 'FAIL',
      failures,
    }

    const artifactPath =
      process.env
        .LOGRES_VERIFY_SHA
        ? path.join(
            '/home/ubuntu/logres/artifacts/performance',
            `${sha}.json`,
          )
        : testInfo.outputPath(
            'logres-performance.json',
          )

    await mkdir(
      path.dirname(
        artifactPath,
      ),
      {
        recursive:
          true,
      },
    )

    await writeFile(
      artifactPath,
      JSON.stringify(
        artifact,
        null,
        2,
      ) +
        '\n',
    )

    await testInfo.attach(
      'logres-performance.json',
      {
        body:
          Buffer.from(
            JSON.stringify(
              artifact,
              null,
              2,
            ),
          ),
        contentType:
          'application/json',
      },
    )

    expect(
      failures,
      failures.join(
        '\n',
      ),
    ).toEqual([])
  },
)
