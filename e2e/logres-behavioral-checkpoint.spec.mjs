import { test } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

async function clickLogical(page, logical) {
  const canvas = page.locator('canvas')
  const box = await canvas.boundingBox()
  if (!box) throw new Error('Game canvas has no bounds')
  await page.mouse.click(
    box.x + logical.x / logical.width * box.width,
    box.y + logical.y / logical.height * box.height,
  )
}

async function tapSelectedWeaponCover(page) {
  const result = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresBattleScene')
    const cover = scene?.weaponCover
    if (!cover?.visible) return null
    const pointer = { x: cover.x, y: cover.y }
    scene.weaponCoverPointerDown = Object.freeze({
      x: cover.x,
      y: cover.y,
    })
    scene.handleWeaponCoverPointerUp(pointer)
    return {
      x: cover.x,
      y: cover.y,
      selectedWeaponSlot: scene?.battleKit?.snapshot()?.selectedWeaponSlot ?? null,
      acceptedCommandCount:
        game.registry.get('logres.playableBattle.authority')?.acceptedCommandCount ?? null,
      provenance:
        game.registry.get('logres.playableBattle.inputProvenance') ?? null,
    }
  })
  if (!result) {
    throw new Error('Selected production weapon cover is unavailable')
  }
  return result
}

test('production playable loop emits canonical behavioral checkpoint', async ({ page, request }) => {
  const field = await request.get(
    '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
  )
  test.skip(
    !field.ok() ||
      !(field.headers()['content-type'] ?? '').includes('application/octet-stream'),
    'Private recovered Global field runtime is not hydrated.',
  )

  const events = []
  await page.goto('/')
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__?.scene)

  await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    game.registry.set(
      'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
      [0, 'Novice', 0, 1, 1, 1, 1, 1],
    )
    game.scene.start('LogresFieldScene')
  })

  await page.waitForFunction(
    () =>
      window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableField.status',
      ) === 'READY',
    undefined,
    { timeout: 20_000 },
  )
  events.push('FIELD_READY')

  const encounter = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresFieldScene')
    const marker = scene.playableEncounterMarker
    const camera = scene.cameras.main
    if (!marker) return null
    return {
      x: camera.x + (marker.x - camera.worldView.x) * camera.zoom,
      y: camera.y + (marker.y - camera.worldView.y) * camera.zoom,
      width: game.scale.width,
      height: game.scale.height,
    }
  })
  if (!encounter) throw new Error('Playable encounter marker is unavailable')
  await clickLogical(page, encounter)

  await page.waitForFunction(
    () => {
      const game = window.__AWAKENED_REALMS_GAME__
      return (
        game.scene.isActive('LogresBattleScene') &&
        game.registry.get('logres.playableBattle.status') === 'ACTIVE'
      )
    },
    undefined,
    { timeout: 10_000 },
  )
  events.push('BATTLE_ACTIVE')

  const plan = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const presentation = game.registry.get('logres.battle.presentation')
    const authority = game.registry.get('logres.playableBattle.authority')
    const scene = game.scene.getScene('LogresBattleScene')
    const panels = presentation?.weaponPanels
    if (!Array.isArray(panels) || panels.length !== 5) return null
    const eligible = panels.filter(
      panel =>
        panel?.unlocked === true &&
        panel.weaponRef &&
        panel.normalSkillRef &&
        (panel.specialSkillRef == null || panel.specialEpCost == null),
    )
    if (eligible.length !== 1) return null
    const slot = eligible[0].slotIndex
    if (!Number.isInteger(slot) || slot < 0 || slot > 4) return null
    if (scene?.battleKit?.snapshot()?.selectedWeaponSlot !== slot) return null
    if (!authority || !Number.isInteger(authority.victoryThreshold)) return null
    if (!scene?.weaponCover?.visible) return null
    return {
      x: scene.weaponCover.x,
      y: scene.weaponCover.y,
      width: game.scale.width,
      height: game.scale.height,
      threshold: authority.victoryThreshold,
      accepted: authority.acceptedCommandCount ?? 0,
    }
  })
  if (!plan) throw new Error('Playable weapon-panel command plan is unavailable')

  for (let expected = plan.accepted + 1; expected <= plan.threshold; expected += 1) {
    await tapSelectedWeaponCover(page)
    await page.waitForFunction(
      expectedCount => {
        const registry = window.__AWAKENED_REALMS_GAME__.registry
        const status = registry.get('logres.playableBattle.status')
        const authority = registry.get('logres.playableBattle.authority')
        return (
          status === 'FIELD_RETURN_READY' ||
          (Number.isInteger(authority?.acceptedCommandCount) &&
            authority.acceptedCommandCount >= expectedCount)
        )
      },
      expected,
      { timeout: 10_000 },
    )
  }

  await page.waitForFunction(
    () =>
      window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableBattle.status',
      ) === 'FIELD_RETURN_READY',
    undefined,
    { timeout: 10_000 },
  )
  events.push('BATTLE_VICTORY_READY')
  events.push('FIELD_RETURN_READY')

  const beforeReturn = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const registry = game.registry
    const scene = game.scene.getScene('LogresBattleScene')
    const button = scene.demoReturnButton
    const inventory = registry.get('logres.playableBattle.inventory')
    const authority = registry.get('logres.playableBattle.authority')
    return {
      returnPoint: button
        ? {
            x: button.x,
            y: button.y,
            width: game.scale.width,
            height: game.scale.height,
          }
        : null,
      rewardApplied: registry.get('logres.playableBattle.rewardApplied'),
      resolutionPhase: registry.get('logres.playableBattle.resolution')?.phase,
      inputProvenance: registry.get('logres.playableBattle.inputProvenance'),
      authorityPhase: authority?.phase,
      inventoryRevision: inventory?.revision,
    }
  })
  if (!beforeReturn.returnPoint) {
    throw new Error('Production field-return control is unavailable')
  }
  await clickLogical(page, beforeReturn.returnPoint)

  await page.waitForFunction(
    () => {
      const game = window.__AWAKENED_REALMS_GAME__
      return (
        game.scene.isActive('LogresFieldScene') &&
        game.registry.get('logres.playableField.status') === 'READY'
      )
    },
    undefined,
    { timeout: 20_000 },
  )
  events.push('FIELD_READY_RETURNED')

  const afterReturn = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    return {
      mapId: game.registry.get('logres.playableField.mapId'),
      returnScene: game.scene.isActive('LogresFieldScene')
        ? 'LogresFieldScene'
        : null,
    }
  })

  const observed = {
    events,
    final_state: {
      mapId: afterReturn.mapId,
      rewardApplied: beforeReturn.rewardApplied,
      resolutionPhase: beforeReturn.resolutionPhase,
      inputProvenance: beforeReturn.inputProvenance,
      authorityPhase: beforeReturn.authorityPhase,
      inventoryRevision: beforeReturn.inventoryRevision,
      returnScene: afterReturn.returnScene,
    },
  }

  const output = process.env.LOGRES_BEHAVIOR_TRACE_OUT
  if (!output) {
    throw new Error('LOGRES_BEHAVIOR_TRACE_OUT is required')
  }
  await writeFile(output, JSON.stringify(observed, null, 2) + '\n')
})
