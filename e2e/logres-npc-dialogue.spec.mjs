import {
  expect,
  test,
} from '@playwright/test'

async function canvasObjectPoint(
  page,
  getter,
) {
  const logical =
    await page.evaluate(
      getter,
    )

  if (!logical) {
    throw new Error(
      'Expected Logres field object is unavailable.',
    )
  }

  const box =
    await page
      .locator(
        'canvas',
      )
      .boundingBox()

  if (!box) {
    throw new Error(
      'Game canvas has no bounds.',
    )
  }

  return {
    x:
      box.x +
      (
        logical.x /
        logical.width
      ) *
        box.width,
    y:
      box.y +
      (
        logical.y /
        logical.height
      ) *
        box.height,
  }
}

async function npcMarkerPoint(
  page,
) {
  return canvasObjectPoint(
    page,
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
          .playableNpcMarker

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
}

async function dialogueSurfacePoint(
  page,
) {
  return canvasObjectPoint(
    page,
    () => {
      const game =
        window
          .__AWAKENED_REALMS_GAME__

      const scene =
        game.scene.getScene(
          'LogresFieldScene',
        )

      const surface =
        scene
          .playableNpcDialogueSurface

      if (!surface) {
        return null
      }

      const camera =
        scene
          .cameras
          .main

      return {
        x:
          camera.x +
          (
            surface.x -
            camera.worldView.x
          ) *
            camera.zoom,
        y:
          camera.y +
          (
            surface.y -
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
}

async function closeDialogue(
  page,
) {
  for (
    let index =
      0;
    index <
      2;
    index +=
      1
  ) {
    const point =
      await dialogueSurfacePoint(
        page,
      )

    await page.mouse.click(
      point.x,
      point.y,
    )

    if (
      index ===
      0
    ) {
      await page.waitForFunction(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.playableField.npcDialogue',
            )
            ?.lineIndex ===
          1,
      )
    }
  }
}

test(
  'visible field NPC repeats reconstructed dialogue without duplicating encounter or listener state',
  async ({
    page,
    request,
  }) => {
    const candidate =
      await request.get(
        '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
      )

    const contentType =
      candidate.headers()[
        'content-type'
      ] ??
      ''

    test.skip(
      !candidate.ok() ||
        !contentType.includes(
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
      () => {
        const registry =
          window
            .__AWAKENED_REALMS_GAME__
            .registry

        return (
          registry.get(
            'logres.playableField.status',
          ) ===
            'READY' &&
          registry.get(
            'logres.playableField.npcStatus',
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

    const baseline =
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
            encounterStatus:
              game.registry.get(
                'logres.playableField.encounterStatus',
              ),
            encounterCoord:
              game.registry.get(
                'logres.playableField.encounterCoord',
              ),
            encounterListeners:
              scene
                .playableEncounterMarker
                ?.listenerCount(
                  'pointerdown',
                ) ??
              0,
            npcListeners:
              scene
                .playableNpcMarker
                ?.listenerCount(
                  'pointerdown',
                ) ??
              0,
          }
        },
      )

    expect(
      baseline.encounterStatus,
    ).toBe(
      'READY',
    )

    expect(
      baseline.encounterListeners,
    ).toBe(
      1,
    )

    expect(
      baseline.npcListeners,
    ).toBe(
      1,
    )

    for (
      let session =
        1;
      session <=
        2;
      session +=
        1
    ) {
      const npcPoint =
        await npcMarkerPoint(
          page,
        )

      await page.mouse.click(
        npcPoint.x,
        npcPoint.y,
      )

      await page.waitForFunction(
        () =>
          window
            .__AWAKENED_REALMS_GAME__
            .registry
            .get(
              'logres.playableField.npcDialogue',
            )
            ?.phase ===
          'DIALOGUE_OPEN',
        undefined,
        {
          timeout:
            10_000,
        },
      )

      const openState =
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

            return {
              status:
                registry.get(
                  'logres.playableField.npcStatus',
                ),
              intent:
                registry.get(
                  'logres.playableField.npcTalkIntent',
                ),
              response:
                registry.get(
                  'logres.playableField.npcTalkResponseStub',
                ),
              evidence:
                registry.get(
                  'logres.playableField.npcDialogueEvidence',
                ),
              dialogue:
                registry.get(
                  'logres.playableField.npcDialogue',
                ),
              presentation:
                registry.get(
                  'logres.playableField.npcDialoguePresentation',
                ),
              encounterStatus:
                registry.get(
                  'logres.playableField.encounterStatus',
                ),
              encounterCoord:
                registry.get(
                  'logres.playableField.encounterCoord',
                ),
              battleActive:
                game.scene.isActive(
                  'LogresBattleScene',
                ),
              dialogueListeners:
                scene
                  .playableNpcDialogueSurface
                  ?.listenerCount(
                    'pointerdown',
                  ) ??
                0,
              encounterListeners:
                scene
                  .playableEncounterMarker
                  ?.listenerCount(
                    'pointerdown',
                  ) ??
                0,
              npcListeners:
                scene
                  .playableNpcMarker
                  ?.listenerCount(
                    'pointerdown',
                  ) ??
                0,
            }
          },
        )

      expect(
        openState,
      ).toMatchObject({
        status:
          'DIALOGUE_OPEN',
        intent: {
          provenance:
            'RECONSTRUCTED',
          npcKey:
            'reconstructed-millennium-tree-guide',
          characterRef:
            null,
        },
        response: {
          provenance:
            'RECONSTRUCTED_SERVER_AUTHORITY_STUB',
          rawCode:
            0,
          interpretation:
            'LOCAL_DIALOGUE_OPEN_STUB',
          historicalResponseCodeMeaning:
            'UNRESOLVED',
        },
        evidence: {
          requestMessage:
            'C_GMCL_CHAR_TALK_REQ',
          responseHandler:
            'C_GMCL_CHAR_TALK_REQ_Response',
          dialogueWindow:
            'NpcDialogueWindow',
          exactHistoricalDialoguePayload:
            'UNRESOLVED',
        },
        dialogue: {
          provenance:
            'RECONSTRUCTED_SCRIPT',
          phase:
            'DIALOGUE_OPEN',
          lineIndex:
            0,
          lineCount:
            2,
          completedSessions:
            session -
            1,
          historicalGlobalPayload:
            'UNRESOLVED',
        },
        presentation: {
          mode:
            'RECONSTRUCTED_SCRIPT',
          historicalGlobalDialoguePayload:
            'UNRESOLVED',
          visibleSurfaceCount:
            1,
        },
        encounterStatus:
          baseline
            .encounterStatus,
        encounterCoord:
          baseline
            .encounterCoord,
        battleActive:
          false,
        dialogueListeners:
          1,
        encounterListeners:
          1,
        npcListeners:
          1,
      })

      await closeDialogue(
        page,
      )

      await page.waitForFunction(
        expected =>
          (
            window
              .__AWAKENED_REALMS_GAME__
              .registry
              .get(
                'logres.playableField.npcStatus',
              ) ===
              'READY' &&
            window
              .__AWAKENED_REALMS_GAME__
              .registry
              .get(
                'logres.playableField.npcDialogue',
              )
              ?.completedSessions ===
              expected
          ),
        session,
      )

      const closedState =
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

            return {
              dialogue:
                registry.get(
                  'logres.playableField.npcDialogue',
                ),
              presentation:
                registry.get(
                  'logres.playableField.npcDialoguePresentation',
                ),
              encounterStatus:
                registry.get(
                  'logres.playableField.encounterStatus',
                ),
              encounterCoord:
                registry.get(
                  'logres.playableField.encounterCoord',
                ),
              battleActive:
                game.scene.isActive(
                  'LogresBattleScene',
                ),
              dialogueSurface:
                Boolean(
                  scene
                    .playableNpcDialogueSurface,
                ),
              encounterListeners:
                scene
                  .playableEncounterMarker
                  ?.listenerCount(
                    'pointerdown',
                  ) ??
                0,
              npcListeners:
                scene
                  .playableNpcMarker
                  ?.listenerCount(
                    'pointerdown',
                  ) ??
                0,
            }
          },
        )

      expect(
        closedState,
      ).toMatchObject({
        dialogue: {
          phase:
            'READY',
          currentLine:
            null,
          completedSessions:
            session,
          interaction: {
            requestPending:
              false,
            talkGateActive:
              false,
          },
        },
        presentation: {
          visibleSurfaceCount:
            0,
        },
        encounterStatus:
          baseline
            .encounterStatus,
        encounterCoord:
          baseline
            .encounterCoord,
        battleActive:
          false,
        dialogueSurface:
          false,
        encounterListeners:
          1,
        npcListeners:
          1,
      })
    }
  },
)
