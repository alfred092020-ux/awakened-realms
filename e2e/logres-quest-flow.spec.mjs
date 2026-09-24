import {
  expect,
  test,
} from '@playwright/test'

async function waitForScene(
  page,
  sceneName,
) {
  await page.waitForFunction(
    (name) =>
      window
        .__AWAKENED_REALMS_GAME__
        ?.scene
        .isActive(
          name,
        ),
    sceneName,
  )
}

test(
  'quest tutorial flow keeps explicit placement and rejected invalid quest-start events',
  async ({
    page,
  }) => {
    await page.goto(
      '/',
    )

    await page.waitForFunction(
      () =>
        Boolean(
          window
            .__AWAKENED_REALMS_GAME__
            ?.scene,
        ),
    )

    await page.evaluate(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__
        if (
          !game.scene.isActive(
            'LogresFieldScene',
          )
        ) {
          game.scene.start(
            'LogresFieldScene',
          )
        }
      },
    )

    await waitForScene(
      page,
      'LogresFieldScene',
    )

    const result =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__
          const fieldScene =
            game.scene.getScene(
              'LogresFieldScene',
            )
          const events =
            fieldScene.events
          const registry =
            game.registry

          let rejectedMessage =
            null

          events.once(
            'logres-tutorial-quest-start-rejected',
            (payload) => {
              rejectedMessage =
                payload?.message ??
                null
            },
          )

          events.emit(
            'logres-tutorial-quest-start-show',
            {},
          )

          events.emit(
            'logres-tutorial-quest-start-show',
            {
              centerX:
                360,
              centerY:
                220,
            },
          )

          const questLayer =
            fieldScene.children.list.find(
              (child) =>
                child.type ===
                  'Container' &&
                child.list?.some(
                  (entry) =>
                    entry.texture
                      ?.key ===
                    'logres-global-tutorial-quest-start-text',
                ),
            )

          const wasVisibleAfterShow =
            Boolean(
              questLayer
                ?.visible,
            )

          events.emit(
            'logres-tutorial-quest-start-hide',
          )

          return {
            positioning:
              registry.get(
                'logres.tutorialHud.questStart.positioning',
              ),
            rejectedMessage,
            wasVisibleAfterShow,
          }
        },
      )

    await page.waitForFunction(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__
        const fieldScene =
          game.scene.getScene(
            'LogresFieldScene',
          )
        const questLayer =
          fieldScene.children.list.find(
            (child) =>
              child.type ===
                'Container' &&
              child.list?.some(
                (entry) =>
                  entry.texture
                    ?.key ===
                  'logres-global-tutorial-quest-start-text',
              ),
          )

        return !questLayer?.visible
      },
    )

    const visibleAfterHide =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__
          const fieldScene =
            game.scene.getScene(
              'LogresFieldScene',
            )
          const questLayer =
            fieldScene.children.list.find(
              (child) =>
                child.type ===
                  'Container' &&
                child.list?.some(
                  (entry) =>
                    entry.texture
                      ?.key ===
                    'logres-global-tutorial-quest-start-text',
                ),
            )

          return Boolean(
            questLayer
              ?.visible,
          )
        },
      )

    expect(
      {
        ...result,
        visibleAfterHide,
      },
    ).toEqual({
      positioning:
        'EXPLICIT_CALLER_PLACEMENT_UNTIL_LFLA_TRANSFORM_IS_DECODED',
      rejectedMessage:
        'Quest Start centerX must be a finite number',
      wasVisibleAfterShow:
        false,
      visibleAfterHide:
        false,
    })
  },
)
