import {
  LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES,
  LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS,
} from '../reverse/LogresAssetBehaviorBindingEvidence'
import {
  LOGRES_GLOBAL_3024_AUDIO_CONVENTION,
  LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES,
  LOGRES_GLOBAL_3024_PRESENTATION_UNRESOLVED,
} from '../reverse/LogresGlobal3024PresentationEvidence'
import { LOGRES_GLOBAL_3024_PLATFORM_BRIDGES } from '../reverse/LogresGlobal3024PlatformEvidence'

export type LogresAudioChannel = 'BGM' | 'SE'

export type LogresAudioCue =
  | 'FIELD_BGM'
  | 'FIELD_INTERACTION_SE'
  | 'UI_BGM'
  | 'UI_CONFIRM_SE'
  | 'BATTLE_BGM'
  | 'BATTLE_ACTION_SE'
  | 'BATTLE_RESULT_SE'

export type LogresAudioAuthority =
  | 'CONFIRMED_GLOBAL_RESOURCE'
  | 'CONFIRMED_GLOBAL_RUNTIME'
  | 'SUPPORTED_INFERENCE'
  | 'UNKNOWN'

export interface LogresAudioCueBinding {
  readonly cue: LogresAudioCue
  readonly channel: LogresAudioChannel
  readonly resourcePath: string | null
  readonly authority: LogresAudioAuthority
  readonly rationale: string
}

export interface LogresAudioBackend {
  playBgm(path: string, options: { loop: boolean }): void
  stopBgm(): void
  pauseBgm(): void
  resumeBgm(): void
  fadeOutBgm(seconds: number): void
  playSe(path: string): void
  stopSe?(): void
}

export type LogresAudioDispatch =
  | {
      readonly status: 'PLAYED'
      readonly cue: LogresAudioCue
      readonly channel: LogresAudioChannel
      readonly resourcePath: string
      readonly authority: LogresAudioAuthority
    }
  | {
      readonly status: 'EVIDENCE_CEILING'
      readonly cue: LogresAudioCue
      readonly channel: LogresAudioChannel
      readonly resourcePath: null
      readonly authority: LogresAudioAuthority
      readonly reason: string
    }

const unresolvedSemanticSelection =
  'Global proves audio consumers and resource conventions, but does not prove the dynamic field/UI/battle resource selected for this cue.'

export const LOGRES_AUDIO_REFERENCE_RESOURCES = Object.freeze({
  bgm: Object.freeze({
    channel: 'BGM' as const,
    path: LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalBgm.globalPath,
    authority: 'CONFIRMED_GLOBAL_RESOURCE' as const,
    relation:
      LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalBgm.relation,
  }),
  se: Object.freeze({
    channel: 'SE' as const,
    path: LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalSe.globalPath,
    authority: 'CONFIRMED_GLOBAL_RESOURCE' as const,
    relation:
      LOGRES_ASSET_BEHAVIOR_BINDER_EXACT_RESOURCES.globalSe.relation,
  }),
})

export const LOGRES_AUDIO_CUE_BINDINGS: Readonly<
  Record<LogresAudioCue, LogresAudioCueBinding>
> = Object.freeze({
  FIELD_BGM: Object.freeze({
    cue: 'FIELD_BGM',
    channel: 'BGM',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  FIELD_INTERACTION_SE: Object.freeze({
    cue: 'FIELD_INTERACTION_SE',
    channel: 'SE',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  UI_BGM: Object.freeze({
    cue: 'UI_BGM',
    channel: 'BGM',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  UI_CONFIRM_SE: Object.freeze({
    cue: 'UI_CONFIRM_SE',
    channel: 'SE',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  BATTLE_BGM: Object.freeze({
    cue: 'BATTLE_BGM',
    channel: 'BGM',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  BATTLE_ACTION_SE: Object.freeze({
    cue: 'BATTLE_ACTION_SE',
    channel: 'SE',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
  BATTLE_RESULT_SE: Object.freeze({
    cue: 'BATTLE_RESULT_SE',
    channel: 'SE',
    resourcePath: null,
    authority: 'UNKNOWN',
    rationale: unresolvedSemanticSelection,
  }),
})

export const LOGRES_AUDIO_RUNTIME_EVIDENCE = Object.freeze({
  soundManager:
    LOGRES_GLOBAL_3024_PRESENTATION_PIPELINES.audio,
  bgmConvention:
    LOGRES_GLOBAL_3024_AUDIO_CONVENTION.backgroundMusic,
  seConvention:
    LOGRES_GLOBAL_3024_AUDIO_CONVENTION.soundEffect,
  androidFocusLoss:
    LOGRES_GLOBAL_3024_PLATFORM_BRIDGES.audio,
  unresolved:
    LOGRES_GLOBAL_3024_PRESENTATION_UNRESOLVED,
  selectionGuardrail:
    LOGRES_ASSET_BEHAVIOR_BINDER_GUARDRAILS[0],
})

function assertRecoveredResource(
  channel: LogresAudioChannel,
  path: string,
): void {
  const expectedSuffix = channel === 'BGM' ? '.ogg' : '.wav'
  if (!path.endsWith(expectedSuffix)) {
    throw new Error(
      `Logres ${channel} resource must follow recovered ${expectedSuffix} convention: ${path}`,
    )
  }
}

export class LogresAudioRuntime {
  private readonly backend: LogresAudioBackend
  private currentBgm: string | null = null
  private bgmPaused = false

  constructor(backend: LogresAudioBackend) {
    this.backend = backend
  }

  get state(): Readonly<{
    currentBgm: string | null
    bgmPaused: boolean
  }> {
    return Object.freeze({
      currentBgm: this.currentBgm,
      bgmPaused: this.bgmPaused,
    })
  }

  dispatchCue(cue: LogresAudioCue): LogresAudioDispatch {
    const binding = LOGRES_AUDIO_CUE_BINDINGS[cue]
    if (binding.resourcePath === null) {
      return {
        status: 'EVIDENCE_CEILING',
        cue,
        channel: binding.channel,
        resourcePath: null,
        authority: binding.authority,
        reason: binding.rationale,
      }
    }

    this.playRecoveredResource(
      binding.channel,
      binding.resourcePath,
    )
    return {
      status: 'PLAYED',
      cue,
      channel: binding.channel,
      resourcePath: binding.resourcePath,
      authority: binding.authority,
    }
  }

  playRecoveredResource(
    channel: LogresAudioChannel,
    path: string,
  ): void {
    assertRecoveredResource(channel, path)
    if (channel === 'BGM') {
      this.backend.playBgm(path, { loop: true })
      this.currentBgm = path
      this.bgmPaused = false
      return
    }
    this.backend.playSe(path)
  }

  stopBgm(): void {
    this.backend.stopBgm()
    this.currentBgm = null
    this.bgmPaused = false
  }

  pauseBgm(): void {
    if (this.currentBgm === null || this.bgmPaused) return
    this.backend.pauseBgm()
    this.bgmPaused = true
  }

  resumeBgm(): void {
    if (this.currentBgm === null || !this.bgmPaused) return
    this.backend.resumeBgm()
    this.bgmPaused = false
  }

  handleAudioFocusLoss(): void {
    if (this.currentBgm === null) return
    this.backend.fadeOutBgm(2)
    this.backend.pauseBgm()
    this.bgmPaused = true
  }
}
