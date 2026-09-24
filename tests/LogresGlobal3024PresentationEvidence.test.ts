import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_AUDIO_CONVENTION,
  LOGRES_GLOBAL_3024_BATTLE_PRESENTATION_PRIMITIVES,
  LOGRES_GLOBAL_3024_PRESENTATION_COUNTS,
  LOGRES_GLOBAL_3024_PRESENTATION_GUARDRAIL,
  LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES,
  LOGRES_GLOBAL_3024_PRESENTATION_PROVENANCE,
  LOGRES_GLOBAL_3024_PRESENTATION_RESOURCE_PATHS,
  LOGRES_GLOBAL_3024_SKIT_PRESENTATION_PRIMITIVES,
} from '../src/game/logres/reverse/LogresGlobal3024PresentationEvidence'

describe('Global 3.0.24 presentation evidence', () => {
  it('recovers the core presentation families', () => {
    expect(LOGRES_GLOBAL_3024_PRESENTATION_PROVENANCE)
      .toBe('CONFIRMED_ORIGINAL_GLOBAL_3_0_24_PRESENTATION_RENDER_AUDIO_SURFACE')
    expect(LOGRES_GLOBAL_3024_PRESENTATION_COUNTS.flash)
      .toEqual({ classes: 46, methods: 314 })
    expect(LOGRES_GLOBAL_3024_PRESENTATION_COUNTS.spine)
      .toEqual({ classes: 5, methods: 55 })
    expect(LOGRES_GLOBAL_3024_PRESENTATION_COUNTS.shaderPostEffect)
      .toEqual({ classes: 23, methods: 111 })
  })

  it('recovers exact audio filename conventions', () => {
    expect(LOGRES_GLOBAL_3024_AUDIO_CONVENTION.backgroundMusic.rule)
      .toContain('.ogg')
    expect(LOGRES_GLOBAL_3024_AUDIO_CONVENTION.soundEffect.rule)
      .toContain('.wav')
    expect(LOGRES_GLOBAL_3024_AUDIO_CONVENTION.androidBridge)
      .toHaveLength(2)
  })

  it('recovers Flash, Spine and camera pipelines', () => {
    expect(LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES.flash)
      .toContain('FlashSequencer')
    expect(LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES.spine)
      .toContain('SpineSkeletonResource')
    expect(LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES.camera)
      .toContain('Isometric')
  })

  it('separates battle and skit presentation primitives', () => {
    expect(LOGRES_GLOBAL_3024_BATTLE_PRESENTATION_PRIMITIVES)
      .toContain('damage/guard/miss')
    expect(LOGRES_GLOBAL_3024_SKIT_PRESENTATION_PRIMITIVES)
      .toContain('wait click')
    expect(LOGRES_GLOBAL_3024_PRESENTATION_RESOURCE_PATHS)
      .toContain('shader/field_terrain.vert')
  })

  it('does not promote presentation into gameplay authority', () => {
    expect(LOGRES_GLOBAL_3024_PRESENTATION_GUARDRAIL)
      .toContain('Gameplay authority remains')
  })
})
