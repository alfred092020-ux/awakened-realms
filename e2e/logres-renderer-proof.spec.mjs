import { existsSync } from 'node:fs'
import { test, expect } from '@playwright/test'

test('proof reports missing private assets without entering gameplay', async ({ page }) => {
  await page.route('**/__logres_ref/renderer-proof/**', route => route.fulfill({ status: 404, body: 'Private assets unavailable' }))
  await page.goto('/?rendererProof=1')
  await expect(page.getByRole('status')).toHaveAttribute('data-proof-status', 'error')
  await expect(page.getByRole('status')).toContainText('unavailable')
  expect(await page.evaluate(() => Boolean(window.__AWAKENED_REALMS_GAME__))).toBe(false)
})

test('authentic private map reaches WebGL with both UV policies', async ({ page }, testInfo) => {
  test.skip(!existsSync('public/__logres_ref/renderer-proof/001_000_00002/001_000_00002.map.bin'), 'Requires private hydration')
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('/?rendererProof=1')
  await expect(page.getByRole('status')).toHaveAttribute('data-proof-status', 'ready')
  await expect(page.getByRole('status')).toContainText('triangles')
  const pixels = async () => page.locator('canvas').evaluate(canvas => {
    const gl = canvas.getContext('webgl')
    const bytes = new Uint8Array(canvas.width * canvas.height * 4)
    gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, bytes)
    let visible = 0, checksum = 0
    for (let i = 0; i < bytes.length; i += 4) {
      if (bytes[i] > 30 || bytes[i + 1] > 30 || bytes[i + 2] > 30) visible++
      checksum = (checksum + bytes[i] * (i + 1) + bytes[i + 1]) >>> 0
    }
    return { visible, checksum, error: gl.getError() }
  })
  const original = await pixels()
  expect(original.visible).toBeGreaterThan(10000)
  expect(original.error).toBe(0)
  await page.screenshot({ path: testInfo.outputPath('authentic-terrain-top-left.png') })
  await page.locator('#proof-uv').selectOption('bottom')
  const flipped = await pixels()
  expect(flipped.visible).toBeGreaterThan(10000)
  expect(flipped.checksum).not.toBe(original.checksum)
  expect(flipped.error).toBe(0)
  await page.screenshot({ path: testInfo.outputPath('authentic-terrain-bottom-left.png') })
  await page.locator('#proof-layer').selectOption('chip')
  expect((await pixels()).visible).toBeGreaterThan(10000)
  await page.locator('#proof-layer').selectOption('obj')
  expect((await pixels()).visible).toBeGreaterThan(0)
  await page.locator('canvas').evaluate(canvas => {
    const extension = canvas.getContext('webgl').getExtension('WEBGL_lose_context')
    if (!extension) throw new Error('Test browser must support forced context loss')
    extension.loseContext()
  })
  await expect(page.getByRole('status')).toHaveAttribute('data-proof-status', 'error')
  await page.locator('#proof-uv').selectOption('top')
  await expect(page.getByRole('status')).toHaveAttribute('data-proof-status', 'error')
  expect(errors).toEqual([])
})
