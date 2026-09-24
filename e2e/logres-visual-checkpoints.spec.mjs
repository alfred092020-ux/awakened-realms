import { execFile } from 'node:child_process'
import path from 'node:path'
import { promisify } from 'node:util'
import { expect, test } from '@playwright/test'

const execFileAsync = promisify(execFile)
const verifier = path.resolve('scripts/logres/verify_visual_checkpoint.py')

const REQUIRED_VISUAL_CHECKPOINTS = Object.freeze([
  'title',
  'onboarding',
  'field',
  'npc',
  'battle',
  'victory',
  'menu',
])

async function requirePrivate(request, url, type) {
  const response = await request.get(url)
  const contentType = response.headers()['content-type'] ?? ''
  if (!response.ok() || !contentType.includes(type)) {
    throw new Error(
      `Required private visual runtime missing: ${url} status=${response.status()} type=${contentType}`,
    )
  }
}

async function waitForScene(page, name) {
  await page.waitForFunction(
    sceneName => Boolean(
      window.__AWAKENED_REALMS_GAME__?.scene?.isActive(sceneName),
    ),
    name,
    { timeout: 20_000 },
  )
}

async function logicalPoint(page, getter) {
  const logical = await page.evaluate(getter)
  if (!logical) {
    throw new Error('Required visual checkpoint object is unavailable.')
  }
  const box = await page.locator('canvas').boundingBox()
  if (!box) {
    throw new Error('Game canvas has no bounds.')
  }
  return {
    x: box.x + (logical.x / logical.width) * box.width,
    y: box.y + (logical.y / logical.height) * box.height,
  }
}

async function recordReview(checkpoint, image, metrics) {
  const enabled = ['1', 'true', 'yes'].includes(
    String(process.env.LOGRES_RECORD_VISUAL_TRUTH ?? '').toLowerCase(),
  )
  if (!enabled) {
    return { recorded: false, reason: 'DISABLED' }
  }

  const required = ['1', 'true', 'yes'].includes(
    String(process.env.LOGRES_REQUIRE_VISUAL_TRUTH_RECORD ?? '').toLowerCase(),
  )
  const sha = String(process.env.LOGRES_VERIFY_SHA ?? '')
  if (!/^[0-9a-f]{40}$/.test(sha)) {
    if (required) {
      throw new Error(
        `Visual checkpoint ${checkpoint} requires an exact lowercase SHA.`,
      )
    }
    return { recorded: false, reason: 'INVALID_SHA' }
  }

  const recorder =
    process.env.LOGRES_VISUAL_TRUTH_BIN ??
    '/home/ubuntu/logres/bin/logres-visual-truth'
  const args = [
    'record',
    sha,
    checkpoint,
    image,
    'REVIEW',
    '--viewport',
    JSON.stringify({
      width: 720,
      height: 1280,
      source: 'playwright',
    }),
    '--device',
    JSON.stringify({
      runner: 'canonical-playwright',
      gate: 'visual-fidelity-coverage',
    }),
    '--metrics',
    JSON.stringify({
      ...metrics,
      reference_status: 'MISSING',
      fidelity_verdict: 'REVIEW',
    }),
  ]

  try {
    const result = await execFileAsync(recorder, args, {
      maxBuffer: 1024 * 1024,
    })
    return {
      recorded: true,
      record: JSON.parse(result.stdout),
    }
  } catch (error) {
    if (required) {
      throw error
    }
    return {
      recorded: false,
      reason: 'RECORDER_FAILED',
    }
  }
}

async function captureReview(page, testInfo, checkpoint, mode = 'canvas') {
  const image = testInfo.outputPath(`${checkpoint}.png`)
  if (mode === 'page') {
    await page.screenshot({ path: image })
  } else {
    const canvas = page.locator('canvas')
    await expect(canvas).toBeVisible()
    await canvas.screenshot({ path: image })
  }

  const truth = await recordReview(
    checkpoint,
    image,
    {
      capture_kind: mode,
      measurement: 'SCREENSHOT_CAPTURE',
    },
  )
  await testInfo.attach(`${checkpoint}-visual-truth.json`, {
    body: Buffer.from(JSON.stringify(truth, null, 2)),
    contentType: 'application/json',
  })
}

async function captureAndVerify(page, testInfo, checkpoint) {
  const canvas = page.locator('canvas')
  await expect(canvas).toBeVisible()
  const image = testInfo.outputPath(`${checkpoint}.png`)
  await canvas.screenshot({ path: image })
  let stdout = ''
  try {
    const result = await execFileAsync(
      'python3',
      [verifier, '--checkpoint', checkpoint, '--image', image],
      { maxBuffer: 1024 * 1024 },
    )
    stdout = result.stdout.trim()
  } catch (error) {
    stdout = String(error?.stdout ?? '').trim()
    const stderr = String(error?.stderr ?? '').trim()
    throw new Error(
      `Visual checkpoint ${checkpoint} failed. ${stdout || stderr || error}`,
    )
  }
  const report = JSON.parse(stdout)
  await testInfo.attach(`${checkpoint}-visual-report.json`, {
    body: Buffer.from(JSON.stringify(report, null, 2)),
    contentType: 'application/json',
  })
  expect(report.pass).toBe(true)
}

async function enterPlayableField(page) {
  await page.evaluate(() => {
    window.__AWAKENED_REALMS_GAME__.scene.start('LogresFieldScene')
  })
  await page.waitForFunction(
    () =>
      window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableField.status',
      ) === 'READY',
    undefined,
    { timeout: 20_000 },
  )
  await page.waitForTimeout(250)
}

async function openNpcDialogue(page) {
  await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresFieldScene')

    // Visual coverage exercises the scene-owned dialogue presentation directly.
    // Interaction/pathfinding behavior is verified by logres-npc-dialogue.spec.
    scene.npcDialogueController.openDialogue()
  })
  await page.waitForFunction(
    () =>
      window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableField.npcDialogue',
      )?.phase === 'DIALOGUE_OPEN',
    undefined,
    { timeout: 10_000 },
  )
  await page.waitForTimeout(150)
}

async function enterBattle(page) {
  const point = await logicalPoint(page, () => {
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
  await page.mouse.click(point.x, point.y)
  await waitForScene(page, 'LogresBattleScene')
  await page.waitForTimeout(250)
}

async function showVictory(page) {
  await page.evaluate(() => {
    const game = window.__AWAKENED_REALMS_GAME__
    const scene = game.scene.getScene('LogresBattleScene')
    scene.resolvePlayableBattle()
  })
  await page.waitForFunction(
    () =>
      window.__AWAKENED_REALMS_GAME__.registry.get(
        'logres.playableBattle.status',
      ) === 'FIELD_RETURN_READY',
  )
  await page.waitForTimeout(150)
}

async function showMenu(page) {
  await page.waitForFunction(
    () => Boolean(window.__LOGRES_UI_RUNTIME_FACTORY__),
  )
  await page.evaluate(() => {
    const existing = document.querySelector(
      '[data-logres-ui-runtime="mounted"]',
    )
    if (existing) existing.remove()
    window.__LOGRES_UI_RUNTIME_FACTORY__.mount(document.body)
  })
  const runtime = page.locator(
    '[data-logres-ui-runtime="mounted"]',
  )
  await runtime.locator(
    '[data-logres-action="open-field-menu"]',
  ).click()
  await expect(runtime).toHaveAttribute(
    'data-logres-surface',
    'FIELD_MENU',
  )
}

test(
  'required visual fidelity checkpoints persist evidence-bounded exact-SHA coverage',
  async ({ page, request }, testInfo) => {
    expect(REQUIRED_VISUAL_CHECKPOINTS).toHaveLength(7)

    await requirePrivate(
      request,
      '/__logres_ref/global/gui/title/title_back.dds.png',
      'image/',
    )
    await requirePrivate(
      request,
      '/__logres_ref/global/gui/title/title_ok.png',
      'image/',
    )
    for (const url of [
      '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
      '/__logres_ref/renderer-proof/002_000_00001/chip_d.bin',
      '/__logres_ref/renderer-proof/002_000_00001/object_d.bin',
    ]) {
      await requirePrivate(request, url, 'application/octet-stream')
    }
    await requirePrivate(
      request,
      '/__logres_ref/renderer-proof/002_000_00001/002_000_00001_CHIP.png',
      'image/',
    )
    await requirePrivate(
      request,
      '/__logres_ref/renderer-proof/002_000_00001/002_000_00001_OBJ.png',
      'image/',
    )

    await page.goto('/')
    await waitForScene(page, 'LogresTitleScene')
    await page.waitForFunction(() => {
      const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene(
        'LogresTitleScene',
      )
      return scene.children.list.some(
        child => child.x === 360 && child.y === 1080 && child.alpha === 1,
      )
    })
    await captureAndVerify(page, testInfo, 'title')

    await page.evaluate(() => {
      window.__AWAKENED_REALMS_GAME__.scene.start('LogresTermsScene')
    })
    await waitForScene(page, 'LogresTermsScene')
    await page.waitForTimeout(150)
    await captureReview(page, testInfo, 'onboarding', 'page')

    await enterPlayableField(page)
    await captureAndVerify(page, testInfo, 'field')

    await openNpcDialogue(page)
    await captureReview(page, testInfo, 'npc', 'page')

    await enterPlayableField(page)
    await enterBattle(page)
    await captureAndVerify(page, testInfo, 'battle')

    await showVictory(page)
    await captureReview(page, testInfo, 'victory', 'page')

    await enterPlayableField(page)
    await showMenu(page)
    await captureReview(page, testInfo, 'menu', 'page')
  },
)
