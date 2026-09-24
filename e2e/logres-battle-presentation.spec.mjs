import { expect, test } from '@playwright/test'

test('normal battle has five controls and cannot resolve synthetic rewards', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__?.scene)
  await page.evaluate(() => window.__AWAKENED_REALMS_GAME__.scene.start('LogresBattleScene'))
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__.scene.isActive('LogresBattleScene'))
  const state = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresBattleScene')
    // Exercise the resolver's own guard as well as absence of a visible button.
    scene.resolveDemo01Battle()
    return {
      view: game.registry.get('logres.battle.presentation'),
      controls: scene.children.list.filter(child => child.texture?.key === 'logres-global-skill-base').length,
      demoButton: Boolean(scene.demoResolveButton),
      labels: scene.children.list.filter(child => child.type === 'Text').map(child => child.text),
      inventory: game.registry.get('logres.demo01.inventory') ?? null,
      resolution: game.registry.get('logres.demo01.resolution') ?? null,
    }
  })
  expect(state.controls).toBe(5)
  expect(state.demoButton).toBe(false)
  expect(state.labels.join(' ')).not.toMatch(/DEMO|RESOLVE|VICTORY/)
  expect(state.labels).toContain('RECONSTRUCTED BATTLE')
  await page.locator('canvas').screenshot({ path: testInfo.outputPath('battle-normal.png') })
  expect(state.inventory).toBeNull()
  expect(state.resolution).toBeNull()
  expect(state.view).toMatchObject({
    showDemoControls: false, historicalResult: null, epLabel: 'EP 0',
    provenance: { weaponControlCount: 'CONFIRMED ORIGINAL', historicalResult: 'UNRESOLVED' },
  })
})

test('explicit harness survives battle restart without duplicate rewards or listeners', async ({ page }) => {
  await page.goto('/?logresBattleHarness=1')
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__?.scene)
  await page.evaluate(() => window.__AWAKENED_REALMS_GAME__.scene.start('LogresBattleScene'))
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__.scene.isActive('LogresBattleScene'))

  for (const visit of [0, 1]) {
    const point = await page.evaluate(() => {
      const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresBattleScene')
      return { x: scene.demoResolveButton.x, y: scene.demoResolveButton.y }
    })
    const box = await page.locator('canvas').boundingBox()
    if (!box) throw new Error('Game canvas has no bounds')
    await page.mouse.click(box.x + point.x / 720 * box.width, box.y + point.y / 1280 * box.height)
    await page.waitForFunction(() =>
      window.__AWAKENED_REALMS_GAME__.registry.get('logres.demo01.battleStatus') === 'FIELD_RETURN_READY')
    const resolved = await page.evaluate(() => {
      const game = window.__AWAKENED_REALMS_GAME__
      const scene = game.scene.getScene('LogresBattleScene')
      scene.resolveDemo01Battle() // Duplicate callbacks must not grant again.
      return {
        inventory: game.registry.get('logres.demo01.inventory'),
        rewardApplied: game.registry.get('logres.demo01.rewardApplied'),
        returnEnabled: scene.demoReturnButton?.input?.enabled,
        normalAttackListeners: scene.events.listenerCount('logres-request-normal-attack'),
      }
    })
    expect(resolved.inventory.revision).toBe(1)
    expect(resolved.inventory.entries).toEqual([
      expect.objectContaining({ originalItemId: null, quantity: 1 }),
    ])
    expect(resolved.rewardApplied).toBe(visit === 0)
    expect(resolved.returnEnabled).toBe(true)
    expect(resolved.normalAttackListeners).toBe(1)
    if (visit === 0) {
      await page.evaluate(() =>
        window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresBattleScene').scene.restart({}))
      await page.waitForFunction(() =>
        window.__AWAKENED_REALMS_GAME__.registry.get('logres.demo01.battleStatus') === 'ACTIVE')
    }
  }
})
