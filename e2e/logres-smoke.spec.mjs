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
  'loads strict Logres title and character flow',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    await clickGame(
      page,
      360,
      1110,
    )

    await waitForScene(
      page,
      'LogresCharacterCreateScene',
    )

    const state =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          return {
            titleActive:
              game.scene.isActive(
                'LogresTitleScene',
              ),

            characterActive:
              game.scene.isActive(
                'LogresCharacterCreateScene',
              ),
          }
        },
      )

    expect(
      state.titleActive,
    ).toBe(false)

    expect(
      state.characterActive,
    ).toBe(true)
  },
)
