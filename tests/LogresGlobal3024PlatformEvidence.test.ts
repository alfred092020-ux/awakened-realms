import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_ANDROID_SURFACE,
  LOGRES_GLOBAL_3024_APP_LIFECYCLE,
  LOGRES_GLOBAL_3024_BILLING_PLATFORM,
  LOGRES_GLOBAL_3024_JNI_CALLBACKS,
  LOGRES_GLOBAL_3024_LOCATION_PLATFORM,
  LOGRES_GLOBAL_3024_PLATFORM_BRIDGES,
  LOGRES_GLOBAL_3024_PLATFORM_PROVENANCE,
  LOGRES_GLOBAL_3024_PLATFORM_UNRESOLVED,
  LOGRES_GLOBAL_3024_PUSH_PLATFORM,
  LOGRES_GLOBAL_3024_THIRD_PARTY_BOUNDARY,
} from '../src/game/logres/reverse/LogresGlobal3024PlatformEvidence'

describe('Global 3.0.24 platform evidence', () => {
  it('anchors the Android surface to original Global evidence', () => {
    expect(LOGRES_GLOBAL_3024_PLATFORM_PROVENANCE)
      .toBe('CONFIRMED_ORIGINAL_GLOBAL_3_0_24_ANDROID_JAVA_JNI_PLATFORM_SURFACE')
    expect(LOGRES_GLOBAL_3024_ANDROID_SURFACE.aimingJavaFiles).toBe(33)
    expect(LOGRES_GLOBAL_3024_ANDROID_SURFACE.deepLink.scheme)
      .toBe('logresjrpg')
  })

  it('recovers lifecycle and JNI boundaries', () => {
    expect(LOGRES_GLOBAL_3024_JNI_CALLBACKS).toHaveLength(12)
    expect(LOGRES_GLOBAL_3024_APP_LIFECYCLE.newIntent)
      .toContain('deep-link')
    expect(LOGRES_GLOBAL_3024_JNI_CALLBACKS)
      .toContain('NativeIntent.nativeOnOpenURI(String)')
  })

  it('recovers billing and push behavior', () => {
    expect(LOGRES_GLOBAL_3024_BILLING_PLATFORM.nativeEvents)
      .toContain('OnPurchaseFinished')
    expect(LOGRES_GLOBAL_3024_BILLING_PLATFORM.nativeSurface)
      .toEqual({ classes: 23, methods: 143 })
    expect(LOGRES_GLOBAL_3024_PUSH_PLATFORM.contentKeys)
      .toContain('dialog')
  })

  it('recovers local platform bridges and GPS boundary', () => {
    expect(LOGRES_GLOBAL_3024_PLATFORM_BRIDGES.keychain)
      .toContain('SharedPreferences')
    expect(LOGRES_GLOBAL_3024_LOCATION_PLATFORM.nativeSurface)
      .toEqual({ classes: 12, methods: 108 })
    expect(LOGRES_GLOBAL_3024_LOCATION_PLATFORM.mockDetection)
      .toContain('root/su')
  })

  it('separates third-party code and server-only facts', () => {
    expect(LOGRES_GLOBAL_3024_THIRD_PARTY_BOUNDARY.classification)
      .toBe('THIRD_PARTY_LIBRARIES_WITH_FIRST_PARTY_AIMING_GLUE_ONLY')
    expect(LOGRES_GLOBAL_3024_PLATFORM_UNRESOLVED)
      .toContain('Server-side GPS reward and anti-abuse decisions are not recoverable from Android glue alone.')
  })
})
