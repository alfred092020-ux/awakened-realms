import { describe, expect, it } from 'vitest'

import {
  LOGRES_VIDEO_REFERENCE_ARTIFACT,
  LOGRES_VIDEO_REFERENCE_AUTHORITY_POLICY,
  LOGRES_VIDEO_REFERENCE_CONFLICTS,
  LOGRES_VIDEO_REFERENCE_OBSERVATIONS,
  LOGRES_VIDEO_REFERENCE_RECORDINGS,
  LOGRES_VIDEO_REFERENCE_SCHEMA,
  LOGRES_VIDEO_REFERENCE_UNRESOLVED,
} from '../src/game/logres/reverse/LogresVideoReferenceEvidence'

describe('Logres user-supplied video reference canon', () => {
  it('keeps all supplied recordings version-sensitive until lineage is independently proven', () => {
    expect(LOGRES_VIDEO_REFERENCE_SCHEMA)
      .toBe('logres-video-reference-v1')

    expect(LOGRES_VIDEO_REFERENCE_RECORDINGS.map((entry) => entry.file))
      .toEqual([
        '1000027040.mp4',
        '1000027041.mp4',
        '1000027042.mp4',
      ])

    for (const recording of LOGRES_VIDEO_REFERENCE_RECORDINGS) {
      expect(recording.authority)
        .toBe('VERSION_SENSITIVE_USER_VIDEO')
      expect(recording.global3024Identity)
        .toBe('UNPROVEN')
      expect(recording.currentJpIdentity)
        .toBe('UNPROVEN')
    }
  })

  it('separates confirmed Global authority from current-JP corroboration', () => {
    expect(LOGRES_VIDEO_REFERENCE_AUTHORITY_POLICY.global3024)
      .toMatchObject({
        role: 'PRIMARY_HISTORICAL_AUTHORITY',
        mayConfirmHistoricalGlobal: true,
      })
    expect(LOGRES_VIDEO_REFERENCE_AUTHORITY_POLICY.userSuppliedVideo)
      .toMatchObject({
        role: 'VERSION_SENSITIVE_VISUAL_BEHAVIOR_REFERENCE',
        mayConfirmHistoricalGlobal: false,
      })
    expect(LOGRES_VIDEO_REFERENCE_AUTHORITY_POLICY.currentJp)
      .toMatchObject({
        role: 'CORROBORATION_ONLY',
        mayConfirmHistoricalGlobal: false,
      })
  })

  it('covers the required visible presentation and behavior domains by filename and timestamp', () => {
    const domains = new Set(
      LOGRES_VIDEO_REFERENCE_OBSERVATIONS.map((entry) => entry.domain),
    )

    expect(domains).toEqual(new Set([
      'TITLE',
      'CHARACTER_CREATION',
      'FIELD_HUD',
      'NPC_DIALOGUE',
      'TUTORIAL_GUIDANCE',
      'BATTLE',
      'QUEST_BANNER',
      'TOWN_INTERIOR',
      'MENUS',
      'SYSTEM_CHROME',
    ]))

    for (const observation of LOGRES_VIDEO_REFERENCE_OBSERVATIONS) {
      expect(observation.file).toMatch(/^100002704[012].mp4$/)
      expect(observation.timestampSeconds).toBeGreaterThanOrEqual(0)
      expect(observation.authority)
        .toBe('VERSION_SENSITIVE_USER_VIDEO')
      expect(observation.historicalGlobalClaim)
        .toBe(false)
      expect(observation.observation.trim().length)
        .toBeGreaterThan(20)
    }
  })

  it('records the visible Android navigation-bar divergence without promoting it to Global truth', () => {
    const chrome = LOGRES_VIDEO_REFERENCE_OBSERVATIONS.find(
      (entry) => entry.id === 'visible-android-navigation-bar',
    )
    expect(chrome).toMatchObject({
      file: '1000027041.mp4',
      timestampSeconds: 55.8,
      endTimestampSeconds: 73.7,
      domain: 'SYSTEM_CHROME',
      historicalGlobalClaim: false,
    })
    expect(chrome?.observation)
      .toContain('Android navigation bar')

    const conflict = LOGRES_VIDEO_REFERENCE_CONFLICTS.find(
      (entry) =>
        entry.id === 'system-chrome-vs-current-immersive-reconstruction',
    )
    expect(conflict?.reconstruction)
      .toContain('immersive fullscreen')
    expect(conflict?.globalApkEvidence)
      .toContain('does not establish')
    expect(conflict?.resolution)
      .toContain('not proof')
  })

  it('keeps unresolved lineage and actor/dialogue identity explicit', () => {
    expect(LOGRES_VIDEO_REFERENCE_UNRESOLVED)
      .toContain(
        'Exact build/version/date lineage of 1000027040.mp4, 1000027041.mp4 and 1000027042.mp4.',
      )
    expect(
      LOGRES_VIDEO_REFERENCE_UNRESOLVED.some((value) =>
        value.includes('identity/dialogue text'),
      ),
    ).toBe(true)
    expect(LOGRES_VIDEO_REFERENCE_ARTIFACT)
      .toContain('user-supplied-video-observations-20260925.md')
  })
})

