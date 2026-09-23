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

        /*
         * Preserve the exact reconstructed
         * character-create request tuple so
         * field presentation can resolve the
         * selected gender without inventing a
         * fallback identity.
         */
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
          20_000,
      },
    )

    const state =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const registry =
            game.registry

          const scene =
            game.scene.getScene(
              'LogresFieldScene',
            )

          const player =
            scene.playablePlayer

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

            encounterVisualPresentation:
              registry.get(
                'logres.playableField.encounterVisualPresentation',
              ),

            playerVisualPresentation:
              registry.get(
                'logres.playableField.playerVisualPresentation',
              ),

            playerObject:
              player
                ? {
                    type:
                      player.type,

                    texture:
                      player.texture
                        ?.key ??
                        null,

                    x:
                      player.x,

                    y:
                      player.y,

                    displayWidth:
                      player.displayWidth,

                    displayHeight:
                      player.displayHeight,
                  }
                : null,
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
      state.playerVisualPresentation,
    ).toMatchObject({
      mode:
        'RECOVERED_REFERENCE_ART',

      gender:
        0,

      referenceSex:
        'm',

      source:
        'RECOVERED_CURRENT_JP_PRIVATE_DERIVATIVE',

      bodySelection:
        'RECONSTRUCTED_CURRENT_JP_REFERENCE_BOD_001',

      equipment:
        'NONE',

      historicalGlobalBodyId:
        'UNRESOLVED',

      historicalGlobalEquipmentIds:
        'UNRESOLVED',

      motionApplication:
        'CONFIRMED_CURRENT_JP_RESOURCE',

      scaleSource:
        'PLAYABLE_FIELD_TRANSFORM_FIT',

      anchor:
        'BOTTOM_CENTER_NAVIGATION_TILE',
    })

    expect(
      state.playerObject,
    ).toMatchObject({
      type:
        'Image',

      texture:
        'logres-current-jp-player-avatar-reference-m',

      x:
        expect.any(
          Number,
        ),

      y:
        expect.any(
          Number,
        ),

      displayWidth:
        expect.any(
          Number,
        ),

      displayHeight:
        expect.any(
          Number,
        ),
    })

    expect(
      state.playerObject
        .displayWidth,
    ).toBeGreaterThan(
      0,
    )

    expect(
      state.playerObject
        .displayHeight,
    ).toBeGreaterThan(
      0,
    )

    expect(
      state.encounterVisualPresentation,
    ).toMatchObject({
      mode:
        'RECOVERED_REFERENCE_ART',

      enemy: {
        globalBehavior:
          'CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL',

        historicalGlobalInternalId:
          'UNRESOLVED',
      },

      pointer: {
        globalBehavior:
          'CONFIRMED_GLOBAL_VIDEO_HAND_PROMPT',

        placement:
          'RECONSTRUCTED',
      },
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

    const playerBeforeMove =
      {
        x:
          state.playerObject
            .x,

        y:
          state.playerObject
            .y,
      }

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
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'LogresFieldScene',
            )

          return {
            currentCoord:
              game.registry.get(
                'logres.playableField.currentCoord',
              ),

            player: {
              x:
                scene.playablePlayer
                  .x,

              y:
                scene.playablePlayer
                  .y,

              texture:
                scene.playablePlayer
                  .texture
                  ?.key ??
                  null,
            },
          }
        },
      )

    expect(
      afterMove
        .currentCoord,
    ).not.toEqual(
      beforeMove,
    )

    expect(
      afterMove
        .player
        .texture,
    ).toBe(
      'logres-current-jp-player-avatar-reference-m',
    )

    expect(
      afterMove
        .player,
    ).not.toMatchObject(
      playerBeforeMove,
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
