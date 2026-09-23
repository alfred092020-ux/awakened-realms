import { expect, test } from '@playwright/test'

// CONFIRMED ORIGINAL: Global 3.0.4 launch recording SHA256
// 488e4564622d708f8bd5ff433fb9307ee1eb50f16832d3921242bb5ff3be7d6f,
// 00:38 gender selection, 00:50 temporary Novice in Millennium Tree,
// 09:45 onward permanent registration in Hunter Guild.
// This drives actual pointer input, not direct field scene activation.
async function waitForScene(page, name) {
  await page.waitForFunction(
    name => window.__AWAKENED_REALMS_GAME__?.scene.isActive(name),
    name,
  )
}

async function clickGame(page, x, y) {
  const box = await page.locator('canvas').boundingBox()
  if (!box) throw new Error('Game canvas has no bounds')
  await page.mouse.click(box.x + x / 720 * box.width, box.y + y / 1280 * box.height)
}

for (const gender of [0, 1]) {
  test(`gender ${gender} enters field as temporary Novice before permanent registration`, async ({ page, request }) => {
    const map = await request.get('/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin')
    test.skip(!map.ok() || !map.headers()['content-type']?.includes('application/octet-stream'),
      'Private Global field runtime is not hydrated')
    await page.goto('/')
    await waitForScene(page, 'LogresTitleScene')
    await page.waitForFunction(() => {
      const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresTitleScene')
      return scene.children.list.some(child => child.x === 360 && child.y === 1080 &&
        child.alpha === 1 && child.input?.enabled)
    })
    await clickGame(page, 360, 1080)
    await waitForScene(page, 'LogresWorldSelectScene')
    await page.waitForFunction(() => {
      const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresWorldSelectScene')
      return scene.children.list.some(child => child.type === 'Container' && child.y === 488 &&
        child.alpha === 1 && child.scaleX === 1 && child.input?.enabled)
    })
    await clickGame(page, 360, 488)
    await waitForScene(page, 'LogresCharacterCreateScene')
    await page.waitForFunction(() => {
      const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresCharacterCreateScene')
      return scene.children.list.some(child => child.y === 1152 && child.alpha === 1 && child.input?.enabled)
    })
    if (gender === 1) await clickGame(page, 560, 890)
    // No name/hair/face form is presented before the first field.
    await expect(page.locator('input, textarea, select')).toHaveCount(0)
    await clickGame(page, 360, 1152)
    await waitForScene(page, 'LogresFieldScene')
    await page.waitForFunction(() =>
      window.__AWAKENED_REALMS_GAME__.registry.get('logres.playableField.status') === 'READY')
    const state = await page.evaluate(() => {
      const r = window.__AWAKENED_REALMS_GAME__.registry
      return {
        request: r.get('logres.protocol.C_GMCL_CHAR_CREATE_REQ'),
        identity: r.get('logres.onboarding.identity'),
        accepted: r.get('logres.server.characterCreateResponse')?.accepted,
        map: r.get('logres.playableField.mapId'),
        mapProvenance: r.get('logres.playableField.mapBindingProvenance'),
      }
    })
    expect(state.request.slice(0, 6)).toEqual([0, 'Novice', gender, 1, 1, 1])
    for (const value of state.request.slice(6)) {
      expect(Number.isInteger(value)).toBe(true)
      expect(value).toBeGreaterThanOrEqual(1)
      expect(value).toBeLessThanOrEqual(5)
    }
    expect(state.identity).toEqual({
      name: 'Novice', gender, registration: 'temporary',
      provenance: 'CONFIRMED ORIGINAL',
      permanentRegistrationTrigger: null,
      permanentRegistrationTriggerProvenance: 'UNRESOLVED',
    })
    expect(state.accepted).toBe(true)
    expect(state.map).toBe('002_000_00001')
    expect(state.mapProvenance).toBe('SUPPORTED_INFERENCE')

    if (gender === 1) {
      // Exercise Phaser scene reuse: prior female identity and accepted server
      // response must not authorize a new selection before its own request.
      await page.evaluate(() => {
        const field = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresFieldScene')
        field.scene.start('LogresCharacterCreateScene')
      })
      await waitForScene(page, 'LogresCharacterCreateScene')
      const restarted = await page.evaluate(() => {
        const game = window.__AWAKENED_REALMS_GAME__
        return {
          identity: game.registry.get('logres.onboarding.identity') ?? null,
          request: game.registry.get('logres.protocol.C_GMCL_CHAR_CREATE_REQ') ?? null,
          response: game.registry.get('logres.server.characterCreateResponse') ?? null,
          fieldActive: game.scene.isActive('LogresFieldScene'),
        }
      })
      expect(restarted).toEqual({ identity: null, request: null, response: null, fieldActive: false })
      await page.waitForFunction(() => {
        const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresCharacterCreateScene')
        return scene.children.list.some(child => child.y === 1152 && child.alpha === 1 && child.input?.enabled)
      })
      await clickGame(page, 360, 1152)
      await waitForScene(page, 'LogresFieldScene')
      expect(await page.evaluate(() =>
        window.__AWAKENED_REALMS_GAME__.registry.get('logres.onboarding.identity')?.gender,
      )).toBe(0)
    }
  })
}
