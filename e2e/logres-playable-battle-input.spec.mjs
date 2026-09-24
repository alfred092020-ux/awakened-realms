import { expect, test } from '@playwright/test'

async function canvasPoint(page, logicalX, logicalY) {
  const box = await page.locator('canvas').boundingBox()
  if (!box) throw new Error('Game canvas has no bounds')
  const size = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    return { width: game.scale.width, height: game.scale.height }
  })
  return {
    x: box.x + logicalX / size.width * box.width,
    y: box.y + logicalY / size.height * box.height,
  }
}

test('selected weapon cover distinguishes tap attack from drag selection', async ({ page }) => {
  await page.goto('/')
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__?.scene)

  const layout = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    game.scene.start('LogresBattleScene', {
      weaponPanels: [
        {
          unlocked: true,
          weaponRef: 'weapon-0',
          normalSkillRef: 'normal-0',
          specialSkillRef: null,
          specialEpCost: null,
        },
        {
          unlocked: true,
          weaponRef: 'weapon-1',
          normalSkillRef: 'normal-1',
          specialSkillRef: null,
          specialEpCost: null,
        },
        {
          unlocked: false,
          weaponRef: null,
          normalSkillRef: null,
          specialSkillRef: null,
          specialEpCost: null,
        },
        {
          unlocked: false,
          weaponRef: null,
          normalSkillRef: null,
          specialSkillRef: null,
          specialEpCost: null,
        },
        {
          unlocked: false,
          weaponRef: null,
          normalSkillRef: null,
          specialSkillRef: null,
          specialEpCost: null,
        },
      ],
      selectedWeaponSlot: 0,
      currentEp: 0,
      epCap: null,
    })
    const spacing = 112
    return {
      firstX: game.scale.width / 2 - spacing * 2,
      spacing,
      y: game.scale.height - 150,
    }
  })

  await page.waitForFunction(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const registry = game.registry
    const scene = game.scene.getScene('LogresBattleScene')
    return (
      registry.get('logres.playableBattle.status') === 'ACTIVE' &&
      scene?.weaponCover &&
      scene?.battleKit?.snapshot()?.selectedWeaponSlot === 0
    )
  })

  const cover0 = await page.evaluate(() => {
    const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene(
      'LogresBattleScene',
    )
    return {
      x: scene.weaponCover.x,
      y: scene.weaponCover.y,
    }
  })
  const slot0 = await canvasPoint(page, cover0.x, cover0.y)
  await page.mouse.click(slot0.x, slot0.y)

  await page.waitForFunction(() => {
    const registry = window.__AWAKENED_REALMS_GAME__.registry
    return (
      registry.get('logres.playableBattle.authority')?.acceptedCommandCount === 1
    )
  })

  let state = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const registry = game.registry
    const scene = game.scene.getScene('LogresBattleScene')
    return {
      accepted:
        registry.get('logres.playableBattle.authority')?.acceptedCommandCount,
      provenance:
        registry.get('logres.playableBattle.inputProvenance'),
      selected:
        scene.battleKit?.snapshot()?.selectedWeaponSlot,
    }
  })

  expect(state).toEqual({
    accepted: 1,
    provenance: 'RECONSTRUCTED_PLAYABILITY_FALLBACK',
    selected: 0,
  })

  const slot1 = await canvasPoint(
    page,
    layout.firstX + layout.spacing,
    layout.y,
  )
  await page.mouse.move(slot0.x, slot0.y)
  await page.mouse.down()
  await page.mouse.move(slot1.x, slot1.y, { steps: 8 })
  await page.mouse.up()

  await page.waitForFunction(() =>
    window.__AWAKENED_REALMS_GAME__.scene
      .getScene('LogresBattleScene')
      .battleKit?.snapshot()?.selectedWeaponSlot === 1,
  )

  state = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const registry = game.registry
    const scene = game.scene.getScene('LogresBattleScene')
    return {
      accepted:
        registry.get('logres.playableBattle.authority')?.acceptedCommandCount,
      selected:
        scene.battleKit?.snapshot()?.selectedWeaponSlot,
    }
  })

  expect(state).toEqual({
    accepted: 1,
    selected: 1,
  })

  await page.mouse.click(slot1.x, slot1.y)
  await page.waitForFunction(() =>
    window.__AWAKENED_REALMS_GAME__.registry.get(
      'logres.playableBattle.authority',
    )?.acceptedCommandCount === 2,
  )

  state = await page.evaluate(() => {
    const registry = window.__AWAKENED_REALMS_GAME__.registry
    return {
      accepted:
        registry.get('logres.playableBattle.authority')?.acceptedCommandCount,
      provenance:
        registry.get('logres.playableBattle.inputProvenance'),
      status:
        registry.get('logres.playableBattle.status'),
      demoControls:
        registry.get('logres.battle.presentation')?.showDemoControls,
    }
  })

  expect(state).toEqual({
    accepted: 2,
    provenance: 'RECONSTRUCTED_PLAYABILITY_FALLBACK',
    status: 'ACTIVE',
    demoControls: false,
  })

  await page.mouse.click(slot1.x, slot1.y)
  await page.waitForFunction(() => {
    const registry = window.__AWAKENED_REALMS_GAME__.registry
    return (
      registry.get('logres.playableBattle.authority')?.acceptedCommandCount === 3 &&
      registry.get('logres.playableBattle.status') === 'FIELD_RETURN_READY'
    )
  })

  state = await page.evaluate(() => {
    const registry = window.__AWAKENED_REALMS_GAME__.registry
    return {
      accepted:
        registry.get('logres.playableBattle.authority')?.acceptedCommandCount,
      phase:
        registry.get('logres.playableBattle.authority')?.phase,
      provenance:
        registry.get('logres.playableBattle.inputProvenance'),
      rewardApplied:
        registry.get('logres.playableBattle.rewardApplied'),
      status:
        registry.get('logres.playableBattle.status'),
    }
  })

  expect(state).toEqual({
    accepted: 3,
    phase: 'victory-ready',
    provenance: 'RECONSTRUCTED_PLAYABILITY_FALLBACK',
    rewardApplied: true,
    status: 'FIELD_RETURN_READY',
  })
})
