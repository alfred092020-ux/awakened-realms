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
  'diagnoses recovered title reveal before input',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    const initial =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresTitleScene',
            )

          const control =
            scene.children.list.find(
              (child) =>
                child.x === 360 &&
                child.y === 1080 &&
                child.input,
            )

          return {
            alpha:
              control?.alpha,

            enabled:
              control?.input
                ?.enabled,

            willRender:
              control
                ?.willRender(
                  scene.cameras.main,
                ),
          }
        },
      )

    const logoPresentation =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresTitleScene',
            )

          const logo =
            scene.children.list.find(
              (child) =>
                child.x === 360 &&
                child.y === 367 &&
                child.texture,
            )

          return {
            present:
              Boolean(
                logo,
              ),

            x:
              logo?.x,

            y:
              logo?.y,

            provenance:
              game.registry.get(
                'logres.title.logoPresentation',
              ),
          }
        },
      )

    expect(
      logoPresentation,
    ).toEqual({
      present:
        true,

      x:
        360,

      y:
        367,

      provenance: {
        asset:
          'RECOVERED_GLOBAL',

        layout:
          'SUPPORTED_INFERENCE_CURRENT_JP_LAYOUT',

        nativeEvidence:
          'CONFIRMED_CURRENT_JP_NATIVE',

        animation:
          'UNRESOLVED_GLOBAL_LFLA',
      },
    })

    console.info(
      'TITLE_CONTROL_INITIAL',
      initial,
    )

    expect(
      initial,
    ).toEqual({
      alpha:
        0,

      enabled:
        true,

      willRender:
        false,
    })

    await page.waitForFunction(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__

        const scene =
          game.scene.getScene(
            'LogresTitleScene',
          )

        const control =
          scene.children.list.find(
            (child) =>
              child.x === 360 &&
              child.y === 1080 &&
              child.input,
          )

        return Boolean(
          control &&
          control.alpha === 1 &&
          control.willRender(
            scene.cameras.main,
          ),
        )
      },
    )

    const revealed =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresTitleScene',
            )

          const control =
            scene.children.list.find(
              (child) =>
                child.x === 360 &&
                child.y === 1080 &&
                child.input,
            )

          return {
            alpha:
              control?.alpha,

            willRender:
              control
                ?.willRender(
                  scene.cameras.main,
                ),
          }
        },
      )

    console.info(
      'TITLE_CONTROL_REVEALED',
      revealed,
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

    expect(
      await page.evaluate(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .scene
            .isActive(
              'LogresWorldSelectScene',
            ),
      ),
    ).toBe(true)
  },
)
