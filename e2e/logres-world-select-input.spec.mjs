import {
  expect,
  test,
} from '@playwright/test'

async function waitForScene(
  page,
  sceneName,
) {
  await page.waitForFunction(
    (name) => {
      const game =
        window
          .__AWAKENED_REALMS_GAME__

      return Boolean(
        game &&
        game.scene &&
        game.scene
          .isActive(name),
      )
    },
    sceneName,
  )
}

async function clickGame(
  page,
  x,
  y,
) {
  const canvas =
    page.locator(
      'canvas',
    )

  await expect(
    canvas,
  ).toBeVisible()

  const box =
    await canvas
      .boundingBox()

  if (!box) {
    throw new Error(
      'Game canvas has no bounds.',
    )
  }

  await page.mouse.click(
    box.x +
      (
        x /
        720
      ) *
        box.width,
    box.y +
      (
        y /
        1280
      ) *
        box.height,
  )
}

test(
  'visible World Select card accepts a center tap',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    await page.waitForFunction(
      () => {
        const scene =
          window
            .__AWAKENED_REALMS_GAME__
            .scene
            .getScene(
              'LogresTitleScene',
            )

        return scene
          .children
          .list
          .some(
            (child) =>
              child.x === 360 &&
              child.y === 1080 &&
              child.alpha === 1 &&
              child.input
                ?.enabled,
          )
      },
    )

    await clickGame(
      page,
      360,
      1080,
    )

    await waitForScene(
      page,
      'LogresWorldSelectScene',
    )

    const labelSource =
      await page.evaluate(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.ui.worldSelectLabelSource',
            ),
      )

    expect(
      [
        'RECOVERED_GLOBAL',
        'RECONSTRUCTED_FALLBACK',
      ],
    ).toContain(
      labelSource,
    )

    await page.waitForFunction(
      () => {
        const scene =
          window
            .__AWAKENED_REALMS_GAME__
            .scene
            .getScene(
              'LogresWorldSelectScene',
            )

        return scene
          .children
          .list
          .some(
            (child) =>
              child.type ===
                'Container' &&
              child.y === 488 &&
              child.alpha === 1 &&
              child.scaleX === 1 &&
              child.scaleY === 1 &&
              child.input
                ?.enabled,
          )
      },
    )

    await clickGame(
      page,
      360,
      488,
    )

    await waitForScene(
      page,
      'LogresCharacterCreateScene',
    )

    const selectedWorld =
      await page.evaluate(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.world.selectedId',
            ),
      )

    expect(
      selectedWorld,
    ).toBe(
      1,
    )
  },
)
