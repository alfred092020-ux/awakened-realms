import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const testsDir = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(testsDir, '..')

function readRepoFile(...segments: string[]) {
  return readFileSync(resolve(repoRoot, ...segments), 'utf8')
}

describe('logres android client hardening smoke', () => {
  it('keeps deterministic bridge lifecycle initialization in MainActivity', () => {
    const mainActivity = readRepoFile(
      'android',
      'app',
      'src',
      'main',
      'java',
      'com',
      'nexuscore',
      'awakenedrealms',
      'MainActivity.java',
    )

    expect(mainActivity).toContain('extends BridgeActivity')
    expect(mainActivity).toContain('super.onCreate(savedInstanceState);')
    expect(mainActivity).toContain('if (bridge != null && bridge.getWebView() != null)')
    expect(mainActivity).toContain('setCacheMode(WebSettings.LOAD_NO_CACHE);')
    expect(mainActivity).toContain('clearCache(true);')
    expect(mainActivity).toContain('clearHistory();')
    expect(mainActivity).toContain('reload();')

    const superOnCreateAt = mainActivity.indexOf('super.onCreate(savedInstanceState);')
    const bridgeGuardAt = mainActivity.indexOf('if (bridge != null && bridge.getWebView() != null)')
    expect(superOnCreateAt).toBeGreaterThanOrEqual(0)
    expect(bridgeGuardAt).toBeGreaterThan(superOnCreateAt)
  })

  it('pins Android Capacitor config to mixed-content denial', () => {
    const capacitorConfig = readRepoFile('capacitor.config.ts')
    expect(capacitorConfig).toMatch(/allowMixedContent:\s*false/)
  })

  it('keeps workflow debug signing verification and unsigned release packaging gates', () => {
    const workflow = readRepoFile('.github', 'workflows', 'android-debug-apk.yml')

    expect(workflow).toContain('ANDROID_DEBUG_KEYSTORE_BASE64')
    expect(workflow).toContain('keytool -list -v')
    expect(workflow).toContain('./gradlew assembleDebug assembleRelease --no-daemon')
    expect(workflow).toContain('android/app/build/outputs/apk/debug/app-debug.apk')
    expect(workflow).toContain('android/app/build/outputs/apk/debug/app-debug.apk.sha256')
    expect(workflow).toContain('android/app/build/outputs/apk/release/app-release-unsigned.apk')
    expect(workflow).toContain('android/app/build/outputs/apk/release/app-release-unsigned.apk.sha256')
  })
})
