import {
  expect,
  test,
} from '@playwright/test'

test(
  'hydrated Global candidate reaches playable field runtime',
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
      ] ??
      ''

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

    const state =
      await page.evaluate(
        () => {
          const registry =
            window
              .__AWAKENED_REALMS_GAME__
              .registry

          return {
            status:
              registry.get(
                'logres.playableField.status',
              ),

            mapId:
              registry.get(
                'logres.playableField.mapId',
              ),

            mapBindingProvenance:
              registry.get(
                'logres.playableField.mapBindingProvenance',
              ),

            movementSurfaceComplete:
              registry.get(
                'logres.playableField.movementSurfaceComplete',
              ),

            tileCount:
              registry.get(
                'logres.playableField.tileCount',
              ),

            spawnProvenance:
              registry.get(
                'logres.playableField.spawnProvenance',
              ),

            currentCoord:
              registry.get(
                'logres.playableField.currentCoord',
              ),
          }
        },
      )

    expect(
      state,
    ).toMatchObject({
      status:
        'READY',

      mapId:
        '002_000_00001',

      mapBindingProvenance:
        'SUPPORTED_INFERENCE',

      movementSurfaceComplete:
        true,

      tileCount:
        1380,

      spawnProvenance:
        'RECONSTRUCTED',
    })

    expect(
      state.currentCoord,
    ).toEqual(
      expect.objectContaining({
        col:
          expect.any(
            Number,
          ),
        row:
          expect.any(
            Number,
          ),
        level:
          expect.any(
            Number,
          ),
      }),
    )

    const rasterMetrics =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresFieldScene',
            )

          const source =
            scene.textures
              .get(
                'logres-playable-field-raster',
              )
              .getSourceImage()

          const context =
            source.getContext(
              '2d',
            )

          if (!context) {
            throw new Error(
              'Playable field raster has no 2D context.',
            )
          }

          const pixels =
            context.getImageData(
              0,
              0,
              source.width,
              source.height,
            )
              .data

          let green =
            0

          for (
            let index =
              0;
            index <
              pixels.length;
            index +=
              4
          ) {
            const red =
              pixels[
                index
              ]

            const greenChannel =
              pixels[
                index +
                  1
              ]

            const blue =
              pixels[
                index +
                  2
              ]

            if (
              greenChannel >
                red *
                  1.15 &&
              greenChannel >
                blue *
                  1.1 &&
              greenChannel >
                50
            ) {
              green +=
                1
            }
          }

          return {
            greenRatio:
              green /
              (
                pixels.length /
                4
              ),
          }
        },
      )

    expect(
      rasterMetrics.greenRatio,
    ).toBeGreaterThan(
      0.25,
    )

    const beforeMove =
      state.currentCoord

    const canvas =
      page.locator(
        'canvas',
      )

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
        box.width *
          0.72,
      box.y +
        box.height *
          0.50,
    )

    await page.waitForFunction(
      (
        before,
      ) => {
        const current =
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.playableField.currentCoord',
            )

        return (
          current &&
          (
            current.col !==
              before.col ||
            current.row !==
              before.row
          )
        )
      },
      beforeMove,
      {
        timeout:
          8_000,
      },
    )

    const afterMove =
      await page.evaluate(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.playableField.currentCoord',
            ),
      )

    expect(
      afterMove,
    ).not.toEqual(
      beforeMove,
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
        'Game canvas has no bounds for encounter click.',
      )
    }

    await page.mouse.click(
      encounterBox.x +
        (
          encounterScreen.x /
          720
        ) *
          encounterBox.width,

      encounterBox.y +
        (
          encounterScreen.y /
          1280
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

    const battleState =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          return {
            launchProvenance:
              game.registry.get(
                'logres.playableField.battleLaunchProvenance',
              ),

            kitIdentityProvenance:
              game.registry.get(
                'logres.playableField.battleKitIdentityProvenance',
              ),
          }
        },
      )

    expect(
      battleState,
    ).toEqual({
      launchProvenance:
        'RECONSTRUCTED',

      kitIdentityProvenance:
        'RECONSTRUCTED_LOCAL_IDENTIFIERS',
    })
  },
)
