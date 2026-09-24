import { execFile } from 'node:child_process'
import path from 'node:path'
import { promisify } from 'node:util'
import { expect, test } from '@playwright/test'

const execFileAsync = promisify(execFile)
const verifier = path.resolve('scripts/logres/verify_visual_checkpoint.py')

async function requirePrivate(request, url, type) {
  const response = await request.get(url)
  const contentType = response.headers()['content-type'] ?? ''
  if (!response.ok() || !contentType.includes(type)) {
    throw new Error(`Required private visual runtime missing: ${url} status=${response.status()} type=${contentType}`)
  }
}

async function waitForScene(page, name) {
  await page.waitForFunction(
    sceneName => Boolean(window.__AWAKENED_REALMS_GAME__?.scene?.isActive(sceneName)),
    name,
    { timeout: 20_000 },
  )
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
    throw new Error(`Visual checkpoint ${checkpoint} failed. ${stdout || stderr || error}`)
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
    () => window.__AWAKENED_REALMS_GAME__.registry.get('logres.playableField.status') === 'READY',
    undefined,
    { timeout: 20_000 },
  )
  await page.waitForTimeout(250)
}

async function enterBattle(page) {
  const point = await page.evaluate(() => {
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
  if (!point) throw new Error('Playable encounter marker is unavailable for battle checkpoint.')
  const canvas = page.locator('canvas')
  const box = await canvas.boundingBox()
  if (!box) throw new Error('Game canvas has no bounds for battle checkpoint.')
  await page.mouse.click(
    box.x + (point.x / point.width) * box.width,
    box.y + (point.y / point.height) * box.height,
  )
  await waitForScene(page, 'LogresBattleScene')
  await page.waitForTimeout(250)
}

test('required pre-APK visual checkpoints reject catastrophic render regressions', async ({ page, request }, testInfo) => {
  await requirePrivate(request, '/__logres_ref/global/gui/title/title_back.dds.png', 'image/')
  await requirePrivate(request, '/__logres_ref/global/gui/title/title_ok.png', 'image/')
  for (const url of [
    '/__logres_ref/renderer-proof/002_000_00001/002_000_00001.map.bin',
    '/__logres_ref/renderer-proof/002_000_00001/chip_d.bin',
    '/__logres_ref/renderer-proof/002_000_00001/object_d.bin',
  ]) {
    await requirePrivate(request, url, 'application/octet-stream')
  }
  await requirePrivate(request, '/__logres_ref/renderer-proof/002_000_00001/002_000_00001_CHIP.png', 'image/')
  await requirePrivate(request, '/__logres_ref/renderer-proof/002_000_00001/002_000_00001_OBJ.png', 'image/')

  await page.goto('/')
  await waitForScene(page, 'LogresTitleScene')
  await page.waitForFunction(() => {
    const scene = window.__AWAKENED_REALMS_GAME__.scene.getScene('LogresTitleScene')
    return scene.children.list.some(child => child.x === 360 && child.y === 1080 && child.alpha === 1)
  })
  await captureAndVerify(page, testInfo, 'title')

  await enterPlayableField(page)
  await captureAndVerify(page, testInfo, 'field')

  await enterBattle(page)
  await captureAndVerify(page, testInfo, 'battle')
})
