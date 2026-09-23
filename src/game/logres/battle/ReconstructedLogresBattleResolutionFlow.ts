export const LOGRES_RECONSTRUCTED_BATTLE_RESOLUTION_PROVENANCE =
  'RECONSTRUCTED' as const

export type ReconstructedLogresBattleResolutionPhase =
  | 'battle-active'
  | 'result-received'
  | 'result-presented'
  | 'reward-ready'
  | 'reward-presented'
  | 'field-return-ready'

export interface ReconstructedLogresBattleResultRecord {
  resultRef:
    | string
    | null
  rawOutcomeCode:
    | number
    | null
}

export interface ReconstructedLogresRewardStage {
  rewardKey:
    | string
    | null
  originalRewardRef:
    | string
    | null
  inventoryProjectionRef:
    | string
    | null
}

export interface ReconstructedLogresFieldOverlayIntent {
  overlayKey: string
  originalQuestRef:
    | string
    | null
}

function optionalRef(
  value:
    | string
    | null,
  label: string,
): string | null {
  if (value === null) {
    return null
  }

  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      `${label} must be null or non-empty`,
    )
  }

  return normalized
}

function optionalSafeInteger(
  value:
    | number
    | null,
  label: string,
): number | null {
  if (value === null) {
    return null
  }

  if (
    !Number.isSafeInteger(
      value,
    )
  ) {
    throw new Error(
      `${label} must be null or a safe integer`,
    )
  }

  return value
}

export class ReconstructedLogresBattleResolutionFlow {
  private phase:
    ReconstructedLogresBattleResolutionPhase =
      'battle-active'

  private readonly battleSystemRef:
    | string
    | null

  private result:
    Readonly<ReconstructedLogresBattleResultRecord> | null =
      null

  private reward:
    Readonly<ReconstructedLogresRewardStage> | null =
      null

  private fieldOverlay:
    Readonly<ReconstructedLogresFieldOverlayIntent> | null =
      null

  constructor(
    battleSystemRef:
      | string
      | null,
  ) {
    this.battleSystemRef =
      optionalRef(
        battleSystemRef,
        'Battle resolution battleSystemRef',
      )
  }

  recordResult(
    input:
      ReconstructedLogresBattleResultRecord,
  ): void {
    if (
      this.phase !==
      'battle-active'
    ) {
      throw new Error(
        'Battle result can only be recorded from active battle',
      )
    }

    this.result =
      Object.freeze({
        resultRef:
          optionalRef(
            input.resultRef,
            'Battle resultRef',
          ),
        rawOutcomeCode:
          optionalSafeInteger(
            input.rawOutcomeCode,
            'Battle raw outcome code',
          ),
      })

    this.phase =
      'result-received'
  }

  markResultPresented():
    void {
    if (
      this.phase !==
      'result-received'
    ) {
      throw new Error(
        'Battle result must be received before presentation',
      )
    }

    this.phase =
      'result-presented'
  }

  recordRewardStage(
    input:
      ReconstructedLogresRewardStage,
  ): void {
    if (
      this.phase !==
      'result-presented'
    ) {
      throw new Error(
        'Reward stage must remain separate from battle result presentation',
      )
    }

    this.reward =
      Object.freeze({
        rewardKey:
          optionalRef(
            input.rewardKey,
            'Reward key',
          ),
        originalRewardRef:
          optionalRef(
            input.originalRewardRef,
            'Original reward ref',
          ),
        inventoryProjectionRef:
          optionalRef(
            input.inventoryProjectionRef,
            'Inventory projection ref',
          ),
      })

    this.phase =
      'reward-ready'
  }

  markRewardPresented():
    void {
    if (
      this.phase !==
      'reward-ready'
    ) {
      throw new Error(
        'Reward stage is not ready for presentation',
      )
    }

    this.phase =
      'reward-presented'
  }

  markFieldReturnReady():
    void {
    if (
      this.phase !==
      'reward-presented'
    ) {
      throw new Error(
        'Field return requires reward stage completion',
      )
    }

    this.phase =
      'field-return-ready'
  }

  queueFieldOverlay(
    input:
      ReconstructedLogresFieldOverlayIntent,
  ): Readonly<ReconstructedLogresFieldOverlayIntent> {
    if (
      this.phase !==
      'field-return-ready'
    ) {
      throw new Error(
        'Field overlay can only be queued after return-to-field is ready',
      )
    }

    const overlayKey =
      input.overlayKey.trim()

    if (
      !overlayKey
    ) {
      throw new Error(
        'Field overlay key must be non-empty',
      )
    }

    this.fieldOverlay =
      Object.freeze({
        overlayKey,
        originalQuestRef:
          optionalRef(
            input.originalQuestRef,
            'Field overlay originalQuestRef',
          ),
      })

    return this.fieldOverlay
  }

  snapshot():
    Readonly<{
      provenance:
        typeof LOGRES_RECONSTRUCTED_BATTLE_RESOLUTION_PROVENANCE
      phase:
        ReconstructedLogresBattleResolutionPhase
      battleSystemRef:
        | string
        | null
      result:
        Readonly<ReconstructedLogresBattleResultRecord> | null
      reward:
        Readonly<ReconstructedLogresRewardStage> | null
      fieldOverlay:
        Readonly<ReconstructedLogresFieldOverlayIntent> | null
    }> {
    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_BATTLE_RESOLUTION_PROVENANCE,
      phase:
        this.phase,
      battleSystemRef:
        this.battleSystemRef,
      result:
        this.result,
      reward:
        this.reward,
      fieldOverlay:
        this.fieldOverlay,
    })
  }
}
