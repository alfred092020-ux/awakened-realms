import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_FLASH_PIPELINE,
  LOGRES_GLOBAL_3024_RELEASE_SCENES,
  LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE,
  LOGRES_GLOBAL_3024_SKIT_ACTIONS,
  LOGRES_GLOBAL_3024_UI_SCENE_COUNTS,
  LOGRES_GLOBAL_3024_UI_SCENE_PROVENANCE,
  LOGRES_GLOBAL_3024_UI_SCENE_UNRESOLVED,
} from '../src/game/logres/reverse/LogresGlobal3024UiSceneEvidence'

describe('Global 3.0.24 UI and scene evidence', () => {
  it('anchors the surface to original Global evidence', () => {
    expect(LOGRES_GLOBAL_3024_UI_SCENE_PROVENANCE)
      .toBe('CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_AND_PACKAGED_UI_SURFACE')
    expect(LOGRES_GLOBAL_3024_UI_SCENE_COUNTS.releaseScenes)
      .toEqual({ classes: 14, methods: 222 })
    expect(LOGRES_GLOBAL_3024_UI_SCENE_COUNTS.windowClasses)
      .toEqual({ classes: 338, methods: 2712 })
    expect(LOGRES_GLOBAL_3024_UI_SCENE_COUNTS.packagedUiMembers)
      .toBe(399)
  })

  it('recovers the complete ReleaseScene family', () => {
    expect(LOGRES_GLOBAL_3024_RELEASE_SCENES).toHaveLength(14)
    expect(LOGRES_GLOBAL_3024_RELEASE_SCENES)
      .toContain('ReleaseScene_GameField')
    expect(LOGRES_GLOBAL_3024_RELEASE_SCENES)
      .toContain('ReleaseScene_Battle')
    expect(LOGRES_GLOBAL_3024_RELEASE_SCENES)
      .toContain('ReleaseScene_WorldSelector')
  })

  it('records lifecycle and manager architecture', () => {
    expect(LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE.sceneLifecycle)
      .toContain('onInitializeStart')
    expect(LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE.sceneLifecycle)
      .toContain('onFinalizeEnd')
    expect(LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE.windowManager)
      .toContain('terminateAllWindowSync')
  })

  it('records skit and Flash presentation primitives', () => {
    expect(LOGRES_GLOBAL_3024_SKIT_ACTIONS).toContain('PlayBGM')
    expect(LOGRES_GLOBAL_3024_SKIT_ACTIONS).toContain('WaitClick')
    expect(LOGRES_GLOBAL_3024_FLASH_PIPELINE.runtime)
      .toContain('FlashSequencer')
    expect(LOGRES_GLOBAL_3024_FLASH_PIPELINE.packagedMemberTypes.lfla)
      .toBe(15)
  })

  it('keeps presentation ceilings explicit', () => {
    expect(LOGRES_GLOBAL_3024_UI_SCENE_UNRESOLVED)
      .toContain('Historical hosted web/server text used by some screens is absent from the APK.')
  })
})
