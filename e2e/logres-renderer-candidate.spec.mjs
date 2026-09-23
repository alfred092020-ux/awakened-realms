import {
  expect,
  test,
} from '@playwright/test'

test(
  'candidate diagnostic reports missing private assets without entering gameplay',
  async ({
    page,
  }) => {
    await page.route(
      '**/__logres_ref/renderer-proof/002_000_00001/**',
      (
        route,
      ) =>
        route.fulfill({
          status:
            404,
          body:
            'Private candidate unavailable',
        }),
    )

    await page.goto(
      '/?rendererCandidate=002_000_00001',
    )

    const status =
      page.getByRole(
        'status',
      )

    await expect(
      status,
    ).toHaveAttribute(
      'data-candidate-status',
      'error',
    )
    await expect(
      status,
    ).toContainText(
      'unavailable',
    )

    await expect(
      page.getByText(
        'CANDIDATE_NOT_IDENTIFIED_TUTORIAL',
        {
          exact:
            false,
        },
      ),
    ).toBeVisible()

    expect(
      await page.evaluate(
        () =>
          Boolean(
            window
              .__AWAKENED_REALMS_GAME__,
          ),
      ),
    ).toBe(
      false,
    )
  },
)

test(
  'candidate diagnostic rejects a noncanonical map id without entering gameplay',
  async ({
    page,
  }) => {
    await page.goto(
      '/?rendererCandidate=../../private',
    )
    const status =
      page.getByRole(
        'status',
      )

    await expect(
      status,
    ).toHaveAttribute(
      'data-candidate-status',
      'error',
    )

    await expect(
      status,
    ).toContainText(
      'Invalid Logres map id',
    )

    expect(
      await page.evaluate(
        () =>
          Boolean(
            window
              .__AWAKENED_REALMS_GAME__,
          ),
      ),
    ).toBe(
      false,
    )
  },
)
