import {
  expect,
  test,
} from '@playwright/test'

test(
  'Demo 0.1 completes field -> encounter -> battle -> reward -> field',
  async ({
    page,
    request,
  }) => {
    const candidate =
      await request.get(
        '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
      )

    const candidateContentType =
      candidate.headers()[
        'content-type'
      ] ?? ''

    test.skip(
      !candidate.ok() ||
        !candidateContentType.includes(
          'application/octet-stream',
        ),
      'Private recovered Global field runtime is not hydrated.',
    )

    await page.goto('/')

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
          20_000,
      },
    )

    const canvas =
      page.locator(
        'canvas',
      )

    const encounterScreen =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresFieldScene',
            )

          const marker =
            scene
              .playableEncounterMarker

          const camera =
            scene
              .cameras
              .main

          if (!marker) {
            return null
          }

          return {
            x:
              camera.x +
              (
                marker.x -
                camera.worldView.x
              ) *
                camera.zoom,
            y:
              camera.y +
              (
                marker.y -
                camera.worldView.y
              ) *
                camera.zoom,
            width:
              game.scale.width,
            height:
              game.scale.height,
          }
        },
      )

    if (!encounterScreen) {
      throw new Error(
        'Playable encounter marker is unavailable.',
      )
    }

    const encounterBox =
      await canvas
        .boundingBox()

    if (!encounterBox) {
      throw new Error(
        'Game canvas has no bounds.',
      )
    }

    await page.mouse.click(
      encounterBox.x +
        (
          encounterScreen.x /
          encounterScreen.width
        ) *
          encounterBox.width,
      encounterBox.y +
        (
          encounterScreen.y /
          encounterScreen.height
        ) *
          encounterBox.height,
    )

    await page.waitForFunction(
      () =>
        window
          .__AWAKENED_REALMS_GAME__
          .scene
          .isActive(
            'LogresBattleScene',
          ),
      undefined,
      {
        timeout:
          10_000,
      },
    )

    const resolvePoint =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresBattleScene',
            )

          const button =
            scene
              .demoResolveButton

          if (!button) {
            return null
          }

          return {
            x:
              button.x,
            y:
              button.y,
            width:
              game.scale.width,
            height:
              game.scale.height,
          }
        },
      )

    if (!resolvePoint) {
      throw new Error(
        'Demo resolve control is unavailable.',
      )
    }

    const resolveBox =
      await canvas
        .boundingBox()

    if (!resolveBox) {
      throw new Error(
        'Game canvas has no battle bounds.',
      )
    }

    await page.mouse.click(
      resolveBox.x +
        (
          resolvePoint.x /
          resolvePoint.width
        ) *
          resolveBox.width,
      resolveBox.y +
        (
          resolvePoint.y /
          resolvePoint.height
        ) *
          resolveBox.height,
    )

    await page.waitForFunction(
      () =>
        window
          .__AWAKENED_REALMS_GAME__
          .registry
          .get(
            'logres.demo01.battleStatus',
          ) ===
        'FIELD_RETURN_READY',
    )

    const returnPoint =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresBattleScene',
            )

          const button =
            scene
              .demoReturnButton

          if (!button) {
            return null
          }

          return {
            x:
              button.x,
            y:
              button.y,
            width:
              game.scale.width,
            height:
              game.scale.height,
          }
        },
      )

    if (!returnPoint) {
      throw new Error(
        'Demo field-return control is unavailable.',
      )
    }

    const returnBox =
      await canvas
        .boundingBox()

    if (!returnBox) {
      throw new Error(
        'Game canvas has no return bounds.',
      )
    }

    await page.mouse.click(
      returnBox.x +
        (
          returnPoint.x /
          returnPoint.width
        ) *
          returnBox.width,
      returnBox.y +
        (
          returnPoint.y /
          returnPoint.height
        ) *
          returnBox.height,
    )

    await page.waitForFunction(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__

        return (
          game.scene.isActive(
            'LogresFieldScene',
          ) &&
          game.registry.get(
            'logres.playableField.status',
          ) ===
            'READY'
        )
      },
      undefined,
      {
        timeout:
          20_000,
      },
    )

    const finalState =
      await page.evaluate(
        () => {
          const registry =
            window
              .__AWAKENED_REALMS_GAME__
              .registry

          const inventory =
            registry.get(
              'logres.demo01.inventory',
            )

          return {
            mapId:
              registry.get(
                'logres.playableField.mapId',
              ),
            rewardApplied:
              registry.get(
                'logres.demo01.rewardApplied',
              ),
            phase:
              registry.get(
                'logres.demo01.resolution',
              )?.phase,
            inventoryRevision:
              inventory?.revision,
            inventoryEntries:
              inventory?.entries,
          }
        },
      )

    expect(
      finalState.mapId,
    ).toBe(
      '002_000_00001',
    )

    expect(
      finalState.rewardApplied,
    ).toBe(
      true,
    )

    expect(
      finalState.phase,
    ).toBe(
      'field-return-ready',
    )

    expect(
      finalState.inventoryRevision,
    ).toBe(
      1,
    )

    expect(
      finalState.inventoryEntries,
    ).toEqual([
      expect.objectContaining({
        originalItemId:
          null,
        quantity:
          1,
      }),
    ])
  },
)
