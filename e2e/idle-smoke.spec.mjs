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
  'complete idle roguelike player flow',
  async ({
    page,
  }) => {
    await page.goto('/')

    await waitForScene(
      page,
      'MainMenuScene',
    )

    const canvas =
      page.locator(
        'canvas',
      )

    await expect(
      canvas,
    ).toBeVisible()

    // ENTER REALM
    await clickGame(
      page,
      360,
      883,
    )

    await waitForScene(
      page,
      'AccountScene',
    )

    await page.waitForTimeout(
      250,
    )

    // CONTINUE AS GUEST
    await clickGame(
      page,
      360,
      790,
    )

    await waitForScene(
      page,
      'HubScene',
    )

    // START RUN
    await clickGame(
      page,
      360,
      1175,
    )

    await waitForScene(
      page,
      'RoguelikeBattleScene',
    )

    // Wait for the first real
    // level-up decision.
    await page.waitForFunction(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__

        if (!game) {
          return false
        }

        const scene =
          game.scene.getScene(
            'RoguelikeBattleScene',
          )

        const engine =
          scene.engine

        if (!engine) {
          return false
        }

        return (
          engine
            .getSnapshot()
            .status ===
          'upgrade'
        )
      },
      undefined,
      {
        timeout:
          20000,
      },
    )

    // Choose upgrade card #1.
    await clickGame(
      page,
      360,
      455,
    )

    await page.waitForFunction(
      () => {
        const game =
          window
            .__AWAKENED_REALMS_GAME__

        const scene =
          game?.scene
            .getScene(
              'RoguelikeBattleScene',
            )

        return (
          scene?.engine
            ?.getSnapshot()
            .status ===
          'running'
        )
      },
    )

    // Fast-forward using the
    // real deterministic engine.
    const outcome =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const scene =
            game.scene.getScene(
              'RoguelikeBattleScene',
            )

          const engine =
            scene.engine

          let guard = 0

          while (
            guard <
            10000
          ) {
            guard += 1

            const snapshot =
              engine
                .getSnapshot()

            if (
              snapshot.status ===
              'upgrade'
            ) {
              const first =
                snapshot
                  .pendingUpgrades[0]

              if (!first) {
                throw new Error(
                  'Upgrade choice missing.',
                )
              }

              engine
                .chooseUpgrade(
                  first.id,
                )

              continue
            }

            if (
              snapshot.status ===
                'dead' ||
              snapshot.status ===
                'won'
            ) {
              break
            }

            engine.advance(
              1000,
            )
          }

          const finalSnapshot =
            engine
              .getSnapshot()

          scene.snapshot =
            finalSnapshot

          scene.renderSnapshot(
            finalSnapshot,
          )

          if (
            finalSnapshot.status ===
              'dead' ||
            finalSnapshot.status ===
              'won'
          ) {
            scene.finishRun()
          }

          return {
            status:
              finalSnapshot.status,

            wave:
              finalSnapshot.wave,

            resultVisible:
              scene.resultVisible,
          }
        },
      )

    expect(
      [
        'dead',
        'won',
      ],
    ).toContain(
      outcome.status,
    )

    expect(
      outcome.wave,
    ).toBeGreaterThan(
      1,
    )

    expect(
      outcome.resultVisible,
    ).toBe(true)

    const savedMeta =
      await page.evaluate(
        () =>
          localStorage.getItem(
            'awakened-realms.meta.v1',
          ),
      )

    expect(
      savedMeta,
    ).not.toBeNull()

    const parsed =
      JSON.parse(
        savedMeta,
      )

    expect(
      parsed.lifetimeRuns,
    ).toBeGreaterThanOrEqual(
      1,
    )

    expect(
      parsed.bestWave,
    ).toBeGreaterThan(
      0,
    )
  },
)
