import { expect, test } from '@playwright/test'

const privateBattleStageUrls = [
  '/__logres_ref/current-jp/player-avatar-reference/player_avatar_reference_m.png',
  '/__logres_ref/current-jp/player-avatar-reference/player_avatar_reference_f.png',
  '/__logres_ref/current-jp/tutorial-field/green_jell_idle_0.png',
  '/__logres_ref/current-jp/tutorial-field/green_jell_idle_1.png',
  '/__logres_ref/current-jp/tutorial-field/green_jell_idle_2.png',
  '/__logres_ref/current-jp/tutorial-field/green_jell_idle_3.png',
  '/__logres_ref/current-jp/battle-field/bfd_002_001.png',
]

test('normal battle has visible stage actors, five controls, and cannot resolve synthetic rewards', async ({ page, request }, testInfo) => {
  const responses = await Promise.all(
    privateBattleStageUrls.map(url => request.get(url)),
  )

  const privateReferenceArtPresent = responses
    .slice(0, -1)
    .every(response =>
      response.ok() &&
      (response.headers()['content-type'] ?? '').includes('image/'),
    )

  const battleFieldResponse = responses.at(-1)
  const privateBattleFieldPresent = Boolean(
    battleFieldResponse?.ok() &&
    (battleFieldResponse.headers()['content-type'] ?? '').includes('image/'),
  )

  await page.goto('/')
  await page.waitForFunction(() => window.__AWAKENED_REALMS_GAME__?.scene)

  await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    game.registry.set(
      'logres.protocol.C_GMCL_CHAR_CREATE_REQ',
      [0, 'Novice', 0, 1, 1, 1, 1, 1],
    )
    game.scene.start('LogresBattleScene')
  })

  await page.waitForFunction(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    if (!game?.scene?.isActive('LogresBattleScene')) return false

    return Boolean(
      game.registry.get('logres.battle.stagePresentation') &&
      game.registry.get('logres.battle.presentation'),
    )
  })

  const state = await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresBattleScene')

    // Exercise the resolver's own guard as well as absence of a visible button.
    scene.resolveDemo01Battle()

    return {
      view: game.registry.get('logres.battle.presentation'),
      stage: game.registry.get('logres.battle.stagePresentation'),
      controls:
        game.registry.get('logres.battle.presentation')
          ?.weaponPanels
          ?.length ?? 0,
      stageTextures: scene.children.list
        .map(child => child.texture?.key ?? null)
        .filter(Boolean),
      stageShapeCount: scene.children.list.filter(
        child => child.type === 'Rectangle' || child.type === 'Ellipse',
      ).length,
      demoButton: Boolean(scene.demoResolveButton),
      labels: scene.children.list
        .filter(child => child.type === 'Text')
        .map(child => child.text),
      inventory: game.registry.get('logres.demo01.inventory') ?? null,
      resolution: game.registry.get('logres.demo01.resolution') ?? null,
    }
  })

  expect(state.controls).toBe(5)
  expect(state.demoButton).toBe(false)
  expect(state.labels.join(' ')).not.toMatch(/DEMO|RESOLVE|VICTORY/)
  expect(state.labels.join(' ')).toContain('RECONSTRUCTED BATTLE')
  expect(state.stageShapeCount).toBeGreaterThanOrEqual(
    state.stage.background.mode === 'CURRENT_JP_CANDIDATE' ? 2 : 4,
  )

  expect(state.stage).toMatchObject({
    referenceSex: 'm',
    genderSelection: 'CHARACTER_CREATE_REQUEST',
    provenance: {
      actorSpawnArchitecture: 'CONFIRMED_GLOBAL_3_0_24_NATIVE',
      battlePositionStructure: 'CONFIRMED_GLOBAL_3_0_24_NATIVE_iX_iY',
      battlePositionToScreenTransform: 'UNRESOLVED',
      screenPlacement: 'RECONSTRUCTED',
      battleBackgroundResourceFamily: 'CONFIRMED_GLOBAL_BOUTBG_BFD_PATTERN',
      battleBackgroundCandidate: 'SUPPORTED_INFERENCE_CURRENT_JP_BFD_002_001',
      historicalBattleBackgroundSelection: 'UNRESOLVED',
      stageGroundFallback: 'RECONSTRUCTED_PRESENTATION_ONLY',
      historicalStats: 'UNRESOLVED',
    },
    player: {
      role: 'PLAYER',
      historicalShapeId: 'UNRESOLVED',
      historicalBattlePosition: 'UNRESOLVED',
    },
    enemy: {
      role: 'ENEMY',
      identityProvenance: 'CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL',
      historicalShapeId: 'UNRESOLVED',
      historicalBattlePosition: 'UNRESOLVED',
    },
  })

  if (privateReferenceArtPresent) {
    expect(state.stage.mode).toBe('RECOVERED_REFERENCE_ART')
    expect(state.stageTextures).toContain(
      'logres-current-jp-player-avatar-reference-m',
    )
    expect(
      state.stageTextures.some(
        key =>
          /^logres-current-jp-green-jell-idle-[0-3]$/.test(key),
      ),
    ).toBe(true)
  } else {
    expect(state.stage.mode).toBe('PLACEHOLDER_FALLBACK')
    expect(state.stageTextures).not.toContain(
      'logres-current-jp-player-avatar-reference-m',
    )
  }

  if (privateBattleFieldPresent) {
    expect(state.stage.background).toMatchObject({
      mode: 'CURRENT_JP_CANDIDATE',
      resource: 'battle/field/bfd_002_001.png',
      provenance: 'SUPPORTED_INFERENCE_CURRENT_JP_BFD_002_001',
      historicalGlobalTutorialSelection: 'UNRESOLVED',
    })
    expect(state.stageTextures).toContain(
      'logres-current-jp-battle-field-bfd-002-001',
    )
  } else {
    expect(state.stage.background).toMatchObject({
      mode: 'RECONSTRUCTED_FALLBACK',
      provenance: 'RECONSTRUCTED_PRESENTATION_ONLY',
      historicalGlobalTutorialSelection: 'UNRESOLVED',
    })
    expect(state.stageTextures).not.toContain(
      'logres-current-jp-battle-field-bfd-002-001',
    )
  }

  await page.locator('canvas').screenshot({
    path: testInfo.outputPath('battle-normal.png'),
  })

  expect(state.inventory).toBeNull()
  expect(state.resolution).toBeNull()
  expect(state.view).toMatchObject({
    showDemoControls: false,
    historicalResult: null,
    epLabel: 'EP 0',
    provenance: {
      weaponControlCount: 'CONFIRMED ORIGINAL',
      historicalResult: 'UNRESOLVED',
    },
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
        battleCommandListeners: scene.events.listenerCount('logres-battle-command'),
      }
    })
    expect(resolved.inventory.revision).toBe(1)
    expect(resolved.inventory.entries).toEqual([
      expect.objectContaining({ originalItemId: null, quantity: 1 }),
    ])
    expect(resolved.rewardApplied).toBe(visit === 0)
    expect(resolved.returnEnabled).toBe(true)
    expect(resolved.battleCommandListeners).toBe(1)
    if (visit === 0) {
      await page.evaluate(() =>
        window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresBattleScene').scene.restart({}))
      await page.waitForFunction(() =>
        window.__AWAKENED_REALMS_GAME__.registry.get('logres.demo01.battleStatus') === 'ACTIVE')
    }
  }
})
