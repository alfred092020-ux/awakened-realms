import {
  expect,
  test,
} from '@playwright/test'

test(
  'evidence-bounded field HUD opens and closes the recovered menu surface',
  async ({ page }) => {
    await page.goto('/')

    await page.waitForFunction(
      () =>
        Boolean(
          window
            .__LOGRES_UI_RUNTIME_FACTORY__,
        ),
    )

    await page.evaluate(() => {
      window
        .__LOGRES_UI_RUNTIME_FACTORY__
        .mount(document.body)
    })

    const runtime =
      page.locator(
        '[data-logres-ui-runtime="mounted"]',
      )

    await expect(runtime)
      .toHaveAttribute(
        'data-logres-surface',
        'FIELD_HUD',
      )

    const menuAsset =
      runtime.locator(
        'img[alt="Recovered Logres field menu"]',
      )

    await expect(menuAsset)
      .toHaveAttribute(
        'data-logres-evidence',
        'CONFIRMED ORIGINAL',
      )
    await expect(menuAsset)
      .toHaveAttribute(
        'src',
        '/__logres_ref/global/tutorial-hud/hud/field_menu.png',
      )

    await runtime
      .locator(
        '[data-logres-action="open-field-menu"]',
      )
      .click()

    await expect(runtime)
      .toHaveAttribute(
        'data-logres-surface',
        'FIELD_MENU',
      )
    await expect(runtime)
      .toHaveAttribute(
        'data-logres-stack',
        'FIELD_HUD>FIELD_MENU',
      )
    await expect(
      runtime.locator(
        '[data-logres-ui-evidence]',
      ),
    ).toHaveAttribute(
      'data-logres-ui-evidence',
      'SUPPORTED_INFERENCE',
    )

    await runtime
      .locator(
        '[data-logres-action="close-window"]',
      )
      .click()

    await expect(runtime)
      .toHaveAttribute(
        'data-logres-surface',
        'FIELD_HUD',
      )
    await expect(runtime)
      .toHaveAttribute(
        'data-logres-stack',
        'FIELD_HUD',
      )
  },
)
