import {
  expect,
  test,
} from '@playwright/test'

// CONFIRMED ORIGINAL launch-era Global recording:
// SHA256 488e4564622d708f8bd5ff433fb9307ee1eb50f16832d3921242bb5ff3be7d6f
// shows Terms before Select Gender, then temporary Novice in Millennium Tree.
// Permanent name/hair/face registration occurs later in Hunter Guild.
//
// Global 3.0.24 native evidence also confirms:
// E_GMCL_ACCLOGIN_NOT_AGREEMENT -> AgreementWebView -> agree_to_terms,
// and a real WorldSelector plus saved/default/requested world-ID helpers.
// Therefore first-run E2E must NOT force visible World Select.

async function waitForScene(
  page,
  name,
) {
  await page.waitForFunction(
    (sceneName) =>
      window
        .__AWAKENED_REALMS_GAME__
        ?.scene
        .isActive(
          sceneName,
        ),
    name,
  )
}

async function clickGame(
  page,
  x,
  y,
) {
  const box =
    await page
      .locator(
        'canvas',
      )
      .boundingBox()

  if (!box) {
    throw new Error(
      'Game canvas has no bounds',
    )
  }

  await page.mouse.click(
    box.x +
      x /
        720 *
        box.width,
    box.y +
      y /
        1280 *
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

async function clickCharacterOk(
  page,
) {
  await page.waitForFunction(
    () => {
      const scene =
        window
          .__AWAKENED_REALMS_GAME__
          .scene
          .getScene(
            'LogresCharacterCreateScene',
          )

      return scene
        .children
        .list
        .some(
          (child) =>
            child.y === 1152 &&
            child.alpha === 1 &&
            child.input
              ?.enabled,
        )
    },
  )

  await clickGame(
    page,
    360,
    1152,
  )
}

test(
  'agreement boundary shows neutral player copy without inventing legal text',
  async ({
    page,
  }) => {
    await page.goto(
      '/',
    )

    await waitForScene(
      page,
      'LogresTitleScene',
    )

    await page.evaluate(
      () => {
        window
          .__AWAKENED_REALMS_GAME__
          .scene
          .start(
            'LogresTermsScene',
          )
      },
    )

    await waitForScene(
      page,
      'LogresTermsScene',
    )

    const termsPresentation =
      await page.evaluate(
        () => {
          const game =
            window
              .__AWAKENED_REALMS_GAME__

          const registry =
            game.registry

          const scene =
            game.scene.getScene(
              'LogresTermsScene',
            )

          return {
            hostedPage:
              registry.get(
                'logres.auth.termsHostedPage',
              ),
            presentation:
              registry.get(
                'logres.ui.termsPresentationProvenance',
              ),
            playerCopyStatus:
              registry.get(
                'logres.ui.termsPlayerCopyStatus',
              ),
            visibleText:
              scene.children.list
                .filter(
                  (child) =>
                    typeof child.text === 'string' &&
                    child.visible &&
                    child.alpha > 0,
                )
                .map(
                  (child) =>
                    child.text,
                ),
          }
        },
      )

    expect(
      termsPresentation,
    ).toMatchObject({
      hostedPage:
        'UNRESOLVED',
      presentation:
        'RECONSTRUCTED_WEBVIEW_SHELL',
      playerCopyStatus:
        'NO_LEGAL_COPY_AVAILABLE',
    })

    expect(
      termsPresentation.visibleText,
    ).toEqual(
      expect.arrayContaining([
        'Agreement',
        'Terms of Use',
        'The Terms of Use page is unavailable in this build.\n\nNo legal text is reproduced on this screen.',
        'Continue to proceed.',
        'Continue',
      ]),
    )

    const playerText =
      termsPresentation.visibleText
        .join(
          ' ',
        )
        .toLowerCase()

    for (
      const forbidden of [
        'reconstruction',
        'unresolved',
        'evidence',
        'original global terms',
        'historical hosted page',
      ]
    ) {
      expect(
        playerText,
      ).not.toContain(
        forbidden,
      )
    }
  },
)

for (
  const gender of [
    0,
    1,
  ]
) {
  test(
    `first-run gender ${gender}: Terms -> temporary Novice -> Millennium Tree`,
    async ({
      page,
      request,
    }) => {
      const map =
        await request.get(
          '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
        )

      test.skip(
        !map.ok() ||
          !map
            .headers()[
              'content-type'
            ]
            ?.includes(
              'application/octet-stream',
            ),
        'Private Global field runtime is not hydrated',
      )

      await page.goto(
        '/',
      )

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

      const termsBoundary =
        await page.evaluate(
          () => {
            const game =
              window
                .__AWAKENED_REALMS_GAME__

            const registry =
              game.registry

            const scene =
              game.scene.getScene(
                'LogresTermsScene',
              )

            return {
              loginResult:
                registry.get(
                  'logres.auth.loginResult',
                ),
              agreementScene:
                registry.get(
                  'logres.auth.agreementScene',
                ),
              urlSource:
                registry.get(
                  'logres.auth.termsUrlSource',
                ),
              hostedPage:
                registry.get(
                  'logres.auth.termsHostedPage',
                ),
              presentation:
                registry.get(
                  'logres.ui.termsPresentationProvenance',
                ),
              playerCopyStatus:
                registry.get(
                  'logres.ui.termsPlayerCopyStatus',
                ),
              visibleText:
                scene.children.list
                  .filter(
                    (child) =>
                      typeof child.text === 'string' &&
                      child.visible &&
                      child.alpha > 0,
                  )
                  .map(
                    (child) =>
                      child.text,
                  ),
              worldSelectActive:
                game.scene.isActive(
                  'LogresWorldSelectScene',
                ),
            }
          },
        )

      expect(
        termsBoundary,
      ).toMatchObject({
        loginResult:
          'E_GMCL_ACCLOGIN_NOT_AGREEMENT',
        agreementScene:
          'AgreementWebView',
        urlSource:
          'webViewUrls.terms',
        hostedPage:
          'UNRESOLVED',
        presentation:
          'RECONSTRUCTED_WEBVIEW_SHELL',
        playerCopyStatus:
          'NO_LEGAL_COPY_AVAILABLE',
        worldSelectActive:
          false,
      })

      expect(
        termsBoundary.visibleText,
      ).toEqual(
        expect.arrayContaining([
          'Agreement',
          'Terms of Use',
          'The Terms of Use page is unavailable in this build.\n\nNo legal text is reproduced on this screen.',
          'Continue to proceed.',
          'Continue',
        ]),
      )

      const visibleTermsCopy =
        termsBoundary.visibleText
          .join(
            ' ',
          )
          .toLowerCase()

      for (
        const forbidden of [
          'reconstruction',
          'unresolved',
          'evidence',
          'original global terms',
          'historical hosted page',
        ]
      ) {
        expect(
          visibleTermsCopy,
        ).not.toContain(
          forbidden,
        )
      }

      // Click the reconstructed shell's auth operation. No historical legal
      // copy is fabricated; only the confirmed agree_to_terms boundary exists.
      await clickGame(
        page,
        360,
        1110,
      )

      await waitForScene(
        page,
        'LogresCharacterCreateScene',
      )

      const postAgreement =
        await page.evaluate(
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
              operation:
                registry.get(
                  'logres.auth.lastOperation',
                ),
              worldSelection:
                registry.get(
                  'logres.world.selectionStatus',
                ),
            }
          },
        )

      expect(
        postAgreement,
      ).toEqual({
        accepted:
          true,
        operation:
          'agree_to_terms',
        worldSelection:
          'SKIPPED_CONDITIONAL',
      })

      if (
        gender === 1
      ) {
        await clickGame(
          page,
          560,
          890,
        )
      }

      // Permanent name/hair/face registration must not appear before field.
      await expect(
        page.locator(
          'input, textarea, select',
        ),
      ).toHaveCount(
        0,
      )

      await clickCharacterOk(
        page,
      )

      await waitForScene(
        page,
        'LogresFieldScene',
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
      )

      const state =
        await page.evaluate(
          () => {
            const registry =
              window
                .__AWAKENED_REALMS_GAME__
                .registry

            return {
              request:
                registry.get(
                  'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
                ),
              identity:
                registry.get(
                  'logres.onboarding.identity',
                ),
              accepted:
                registry.get(
                  'logres.server.characterCreateResponse',
                )?.accepted,
              map:
                registry.get(
                  'logres.playableField.mapId',
                ),
              mapProvenance:
                registry.get(
                  'logres.playableField.mapBindingProvenance',
                ),
            }
          },
        )

      expect(
        state.request.slice(
          0,
          6,
        ),
      ).toEqual([
        0,
        'Novice',
        gender,
        1,
        1,
        1,
      ])

      for (
        const value of
          state.request.slice(
            6,
          )
      ) {
        expect(
          Number.isInteger(
            value,
          ),
        ).toBe(
          true,
        )

        expect(
          value,
        ).toBeGreaterThanOrEqual(
          1,
        )

        expect(
          value,
        ).toBeLessThanOrEqual(
          5,
        )
      }

      expect(
        state.identity,
      ).toEqual({
        name:
          'Novice',
        gender,
        registration:
          'temporary',
        provenance:
          'CONFIRMED ORIGINAL',
        permanentRegistrationTrigger:
          null,
        permanentRegistrationTriggerProvenance:
          'UNRESOLVED',
      })

      expect(
        state.accepted,
      ).toBe(
        true,
      )

      expect(
        state.map,
      ).toBe(
        '002_000_00001',
      )

      expect(
        state.mapProvenance,
      ).toBe(
        'SUPPORTED_INFERENCE',
      )

      if (
        gender === 1
      ) {
        // Phaser scene instances are reused. Revisit the gender scene to prove
        // stale accepted authority / identity cannot leak into a new create.
        await page.evaluate(
          () => {
            const field =
              window
                .__AWAKENED_REALMS_GAME__
                .scene
                .getScene(
                  'LogresFieldScene',
                )

            field.scene.start(
              'LogresCharacterCreateScene',
            )
          },
        )

        await waitForScene(
          page,
          'LogresCharacterCreateScene',
        )

        const restarted =
          await page.evaluate(
            () => {
              const game =
                window
                  .__AWAKENED_REALMS_GAME__

              return {
                identity:
                  game.registry.get(
                    'logres.onboarding.identity',
                  ) ??
                  null,
                request:
                  game.registry.get(
                    'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
                  ) ??
                  null,
                response:
                  game.registry.get(
                    'logres.server.characterCreateResponse',
                  ) ??
                  null,
                fieldActive:
                  game.scene.isActive(
                    'LogresFieldScene',
                  ),
              }
            },
          )

        expect(
          restarted,
        ).toEqual({
          identity:
            null,
          request:
            null,
          response:
            null,
          fieldActive:
            false,
        })

        await clickCharacterOk(
          page,
        )

        await waitForScene(
          page,
          'LogresFieldScene',
        )

        expect(
          await page.evaluate(
            () =>
              window
                .__AWAKENED_REALMS_GAME__
                .registry
                .get(
                  'logres.onboarding.identity',
                )
                ?.gender,
          ),
        ).toBe(
          0,
        )
      }
    },
  )
}
