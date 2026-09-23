export const LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE =
  'RECONSTRUCTED' as const

export const LOGRES_GLOBAL_CHAR_TALK_TIME_INTERVAL_SECONDS =
  1.0 as const

export const LOGRES_GLOBAL_CHAR_TALK_LIMIT_INTERVAL_SECONDS =
  5.0 as const

export interface ReconstructedLogresNpcTalkIntent {
  provenance:
    typeof LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE
  npcKey: string
  characterRef:
    | string
    | null
}

export interface ReconstructedLogresNpcInteractionSnapshot {
  provenance:
    typeof LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE
  npcKey:
    | string
    | null
  characterRef:
    | string
    | null
  canTalk: boolean
  inRange: boolean
  requestPending: boolean
  talkGateActive: boolean
  lastResponseCode:
    | number
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

function localKey(
  value: string,
): string {
  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      'NPC key must be non-empty',
    )
  }

  return normalized
}

export class ReconstructedLogresNpcInteractionAuthority {
  private npcKey:
    | string
    | null =
      null

  private characterRef:
    | string
    | null =
      null

  private canTalk =
    false

  private inRange =
    false

  private requestPending =
    false

  private talkGateActive =
    false

  private lastResponseCode:
    | number
    | null =
      null

  setNpcState(
    input: {
      npcKey: string
      characterRef:
        | string
        | null
      canTalk: boolean
      inRange: boolean
    },
  ): void {
    if (
      this.requestPending
    ) {
      throw new Error(
        'Cannot replace NPC state while a talk request is pending',
      )
    }

    this.npcKey =
      localKey(
        input.npcKey,
      )

    this.characterRef =
      optionalRef(
        input.characterRef,
        'NPC characterRef',
      )

    this.canTalk =
      input.canTalk

    this.inRange =
      input.inRange
  }

  createTalkIntent():
    Readonly<ReconstructedLogresNpcTalkIntent> {
    if (
      this.npcKey ===
      null
    ) {
      throw new Error(
        'No NPC is selected for interaction',
      )
    }

    if (
      !this.canTalk
    ) {
      throw new Error(
        'NPC is not currently talkable',
      )
    }

    if (
      !this.inRange
    ) {
      throw new Error(
        'NPC is outside interaction range',
      )
    }

    if (
      this.talkGateActive
    ) {
      throw new Error(
        'NPC talk gate is still active',
      )
    }

    this.requestPending =
      true

    this.talkGateActive =
      true

    this.lastResponseCode =
      null

    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
      npcKey:
        this.npcKey,
      characterRef:
        this.characterRef,
    })
  }

  recordTalkResponse(
    rawCode: number,
  ): void {
    if (
      !this.requestPending
    ) {
      throw new Error(
        'No NPC talk request is pending',
      )
    }

    if (
      !Number.isSafeInteger(
        rawCode,
      )
    ) {
      throw new Error(
        'NPC talk response code must be a safe integer',
      )
    }

    this.requestPending =
      false

    this.lastResponseCode =
      rawCode

    /*
     * Current-JP native keeps the talk gate active after the response and
     * reschedules the release callback. The exact mapping of Global's
     * char_talk_time_interval / char_talk_limit_time_interval to request and
     * response phases is still unresolved, so no timer duration is invented.
     */
  }

  releaseTalkGate():
    void {
    this.talkGateActive =
      false
  }

  snapshot():
    Readonly<ReconstructedLogresNpcInteractionSnapshot> {
    return Object.freeze({
      provenance:
        LOGRES_RECONSTRUCTED_NPC_INTERACTION_PROVENANCE,
      npcKey:
        this.npcKey,
      characterRef:
        this.characterRef,
      canTalk:
        this.canTalk,
      inRange:
        this.inRange,
      requestPending:
        this.requestPending,
      talkGateActive:
        this.talkGateActive,
      lastResponseCode:
        this.lastResponseCode,
    })
  }
}
