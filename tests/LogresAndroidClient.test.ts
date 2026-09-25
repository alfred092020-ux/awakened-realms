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

  it('keeps gameplay immersive while restoring system bars when backgrounded', () => {
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

    expect(mainActivity).toContain('private void enterImmersiveMode()')
    expect(mainActivity).toContain('private void restoreSystemBars()')
    expect(mainActivity).toContain('WindowInsets.Type.statusBars() | WindowInsets.Type.navigationBars()')
    expect(mainActivity).toContain('WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE')
    expect(mainActivity).toContain('View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY')
    expect(mainActivity).toContain('View.SYSTEM_UI_FLAG_HIDE_NAVIGATION')
    expect(mainActivity).toContain('View.SYSTEM_UI_FLAG_FULLSCREEN')
    expect(mainActivity).toContain('public void onResume()')
    expect(mainActivity).toContain('public void onPause()')
    expect(mainActivity).toContain('public void onWindowFocusChanged(boolean hasFocus)')

    const onResumeAt = mainActivity.indexOf('public void onResume()')
    const resumeImmersiveAt = mainActivity.indexOf('enterImmersiveMode();', onResumeAt)
    const onPauseAt = mainActivity.indexOf('public void onPause()')
    const restoreAt = mainActivity.indexOf('restoreSystemBars();', onPauseAt)
    expect(resumeImmersiveAt).toBeGreaterThan(onResumeAt)
    expect(restoreAt).toBeGreaterThan(onPauseAt)
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
