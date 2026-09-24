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

async function clickTitleStart(
  page,
) {
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
}

test(
  'default first-run follows title to Terms and then skips unresolved mandatory World Select semantics',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    await clickTitleStart(
      page,
    )

    await waitForScene(
      page,
      'LogresTermsScene',
    )

    await expect.poll(
      async () =>
        page.evaluate(
          () => {
            const registry =
              window
                .__AWAKENED_REALMS_GAME__
                .registry

            return {
              loginResult:
                registry.get(
                  'logres.auth.loginResult',
                ),
              presentation:
                registry.get(
                  'logres.ui.termsPresentationProvenance',
                ),
              selectionStatus:
                registry.get(
                  'logres.world.selectionStatus',
                ) ?? null,
            }
          },
        ),
    ).toEqual({
      loginResult:
        'E_GMCL_ACCLOGIN_NOT_AGREEMENT',
      presentation:
        'RECONSTRUCTED_WEBVIEW_SHELL',
      selectionStatus:
        null,
    })

    await clickGame(
      page,
      360,
      1110,
    )

    await waitForScene(
      page,
      'LogresCharacterCreateScene',
    )

    await expect.poll(
      async () =>
        page.evaluate(
          () => {
            const registry =
              window
                .__AWAKENED_REALMS_GAME__
                .registry

            return {
              accepted:
                registry.get(
                  'logres.auth.termsAccepted',
                ),
              lastOperation:
                registry.get(
                  'logres.auth.lastOperation',
                ),
              selectionStatus:
                registry.get(
                  'logres.world.selectionStatus',
                ),
              firstRunRequirement:
                registry.get(
                  'logres.world.firstRunRequirement',
                ),
            }
          },
        ),
    ).toEqual({
      accepted:
        true,
      lastOperation:
        'agree_to_terms',
      selectionStatus:
        'SKIPPED_CONDITIONAL',
      firstRunRequirement:
        'CONDITIONAL_NOT_CONFIRMED_MANDATORY',
    })
  },
)

test(
  'forced world-select runtime stays evidence-bounded and transitions to character creation after selection',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    await page.evaluate(() => {
      const registry =
        window.__AWAKENED_REALMS_GAME__.registry

      registry.set(
        'logres.auth.termsAccepted',
        true,
      )

      registry.set(
        'logres.world.selectionRequired',
        true,
      )
    })

    await clickTitleStart(
      page,
    )

    await waitForScene(
      page,
      'LogresWorldSelectScene',
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

    await expect.poll(
      async () =>
        page.evaluate(
          () => {
            const registry =
              window
                .__AWAKENED_REALMS_GAME__
                .registry

            return {
              selectionStatus:
                registry.get(
                  'logres.world.selectionStatus',
                ),
              labelSource:
                registry.get(
                  'logres.ui.worldSelectLabelSource',
                ),
              worldCatalogSource:
                registry.get(
                  'logres.server.worldCatalogSource',
                ),
            }
          },
        ),
    ).toEqual({
      selectionStatus:
        'USER_REQUIRED',
      labelSource:
        'RECONSTRUCTED_FALLBACK',
      worldCatalogSource:
        'RECONSTRUCTED',
    })

    await clickGame(
      page,
      360,
      488,
    )

    await waitForScene(
      page,
      'LogresCharacterCreateScene',
    )

    await expect.poll(
      async () =>
        page.evaluate(
          () => {
            const registry =
              window
                .__AWAKENED_REALMS_GAME__
                .registry

            return {
              selectedWorld:
                registry.get(
                  'logres.world.selectedId',
                ),
              selectionRequired:
                registry.get(
                  'logres.world.selectionRequired',
                ),
              selectionStatus:
                registry.get(
                  'logres.world.selectionStatus',
                ),
            }
          },
        ),
    ).toEqual({
      selectedWorld:
        1,
      selectionRequired:
        false,
      selectionStatus:
        'USER_SELECTED',
    })
  },
)
