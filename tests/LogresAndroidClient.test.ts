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
  it('uses a native Android command-center activity without a WebView bridge', () => {
    const mainActivity = readRepoFile(
      'android', 'app', 'src', 'main', 'java', 'com', 'nexuscore', 'awakenedrealms', 'MainActivity.java',
    )

    expect(mainActivity).toContain('extends Activity')
    expect(mainActivity).toContain('setContentView(R.layout.activity_main)')
    expect(mainActivity).toContain('CredentialManager.create(this)')
    expect(mainActivity).toContain('/api/events')
    expect(mainActivity).toContain('/api/snapshot')
    expect(mainActivity).not.toContain('BridgeActivity')
    expect(mainActivity).not.toContain('getWebView()')
  })

  it('keeps native admin controls gated behind authenticated Nexus access', () => {
    const mainActivity = readRepoFile(
      'android', 'app', 'src', 'main', 'java', 'com', 'nexuscore', 'awakenedrealms', 'MainActivity.java',
    )

    expect(mainActivity).toContain('if(token.isEmpty())')
    expect(mainActivity).toContain('ADMIN LOCKED')
    expect(mainActivity).toContain('Authorization')
    expect(mainActivity).toContain('Bearer ')
  })

  it('uses a no-action-bar post-splash theme with dark transparent system bar surfaces', () => {
    const styles = readRepoFile(
      'android',
      'app',
      'src',
      'main',
      'res',
      'values',
      'styles.xml',
    )

    expect(styles).toContain('<style name="AppTheme.NoActionBar"')
    expect(styles).toContain('<item name="android:statusBarColor">@android:color/transparent</item>')
    expect(styles).toContain('<item name="android:navigationBarColor">@android:color/transparent</item>')
    expect(styles).toContain('<item name="android:windowLightStatusBar">false</item>')
    expect(styles).toContain('<item name="android:windowLightNavigationBar">false</item>')
    expect(styles).toContain('<item name="postSplashScreenTheme">@style/AppTheme.NoActionBar</item>')
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
    expect(workflow).toContain('android/app/build/outputs/apk/release/app-release-unsigned.apk')
  })
})
