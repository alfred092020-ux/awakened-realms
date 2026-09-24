import { describe, expect, it, vi } from 'vitest'

import {
  LOGRES_AUDIO_CUE_BINDINGS,
  LOGRES_AUDIO_REFERENCE_RESOURCES,
  LOGRES_AUDIO_RUNTIME_EVIDENCE,
  LogresAudioRuntime,
  type LogresAudioBackend,
} from '../src/game/logres/audio/LogresAudioRuntime'

function backend(): LogresAudioBackend {
  return {
    playBgm: vi.fn(),
    stopBgm: vi.fn(),
    pauseBgm: vi.fn(),
    resumeBgm: vi.fn(),
    fadeOutBgm: vi.fn(),
    playSe: vi.fn(),
    stopSe: vi.fn(),
  }
}

describe('Logres audio runtime', () => {
  it('preserves exact recovered Global BGM and SE resources', () => {
    expect(LOGRES_AUDIO_REFERENCE_RESOURCES.bgm.path)
      .toBe('sound/bgm/000_000_00001.ogg')
    expect(LOGRES_AUDIO_REFERENCE_RESOURCES.se.path)
      .toBe('sound/se/100_000_00001.wav')
    expect(LOGRES_AUDIO_REFERENCE_RESOURCES.bgm.authority)
      .toBe('CONFIRMED_GLOBAL_RESOURCE')
    expect(LOGRES_AUDIO_REFERENCE_RESOURCES.se.authority)
      .toBe('CONFIRMED_GLOBAL_RESOURCE')
  })

  it('keeps field, UI and battle semantic cue selection at the evidence ceiling', () => {
    expect(Object.keys(LOGRES_AUDIO_CUE_BINDINGS)).toEqual([
      'FIELD_BGM',
      'FIELD_INTERACTION_SE',
      'UI_BGM',
      'UI_CONFIRM_SE',
      'BATTLE_BGM',
      'BATTLE_ACTION_SE',
      'BATTLE_RESULT_SE',
    ])
    for (const binding of Object.values(LOGRES_AUDIO_CUE_BINDINGS)) {
      expect(binding.resourcePath).toBeNull()
      expect(binding.authority).toBe('UNKNOWN')
      expect(binding.rationale).toContain('does not prove')
    }
  })

  it('does not synthesize audio when a semantic mapping is unresolved', () => {
    const sink = backend()
    const runtime = new LogresAudioRuntime(sink)

    expect(runtime.dispatchCue('FIELD_BGM')).toMatchObject({
      status: 'EVIDENCE_CEILING',
      channel: 'BGM',
      resourcePath: null,
    })
    expect(runtime.dispatchCue('UI_CONFIRM_SE')).toMatchObject({
      status: 'EVIDENCE_CEILING',
      channel: 'SE',
      resourcePath: null,
    })
    expect(runtime.dispatchCue('BATTLE_ACTION_SE')).toMatchObject({
      status: 'EVIDENCE_CEILING',
      channel: 'SE',
      resourcePath: null,
    })
    expect(sink.playBgm).not.toHaveBeenCalled()
    expect(sink.playSe).not.toHaveBeenCalled()
  })

  it('plays exact recovered resources through recovered filename conventions', () => {
    const sink = backend()
    const runtime = new LogresAudioRuntime(sink)

    runtime.playRecoveredResource(
      'BGM',
      LOGRES_AUDIO_REFERENCE_RESOURCES.bgm.path,
    )
    runtime.playRecoveredResource(
      'SE',
      LOGRES_AUDIO_REFERENCE_RESOURCES.se.path,
    )

    expect(sink.playBgm).toHaveBeenCalledWith(
      'sound/bgm/000_000_00001.ogg',
      { loop: true },
    )
    expect(sink.playSe).toHaveBeenCalledWith(
      'sound/se/100_000_00001.wav',
    )
    expect(runtime.state).toEqual({
      currentBgm: 'sound/bgm/000_000_00001.ogg',
      bgmPaused: false,
    })
  })

  it('rejects invented resource formats rather than silently remapping them', () => {
    const runtime = new LogresAudioRuntime(backend())

    expect(() =>
      runtime.playRecoveredResource('BGM', 'sound/bgm/fake.mp3'),
    ).toThrow('.ogg')
    expect(() =>
      runtime.playRecoveredResource('SE', 'sound/se/fake.ogg'),
    ).toThrow('.wav')
  })

  it('models recovered SoundManager pause/resume and Android focus-loss behavior', () => {
    const sink = backend()
    const runtime = new LogresAudioRuntime(sink)

    runtime.playRecoveredResource(
      'BGM',
      LOGRES_AUDIO_REFERENCE_RESOURCES.bgm.path,
    )
    runtime.pauseBgm()
    expect(runtime.state.bgmPaused).toBe(true)
    runtime.resumeBgm()
    expect(runtime.state.bgmPaused).toBe(false)
    runtime.handleAudioFocusLoss()

    expect(sink.pauseBgm).toHaveBeenCalledTimes(2)
    expect(sink.resumeBgm).toHaveBeenCalledTimes(1)
    expect(sink.fadeOutBgm).toHaveBeenCalledWith(2)
    expect(runtime.state.bgmPaused).toBe(true)
    expect(LOGRES_AUDIO_RUNTIME_EVIDENCE.androidFocusLoss)
      .toContain('two-second music fade')
  })
})
