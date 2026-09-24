import {
  LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE,
  LOGRES_GLOBAL_3024_BATTLE_SOURCE,
} from './LogresGlobal3024BattleEvidence'

export const LOGRES_GLOBAL_3024_BATTLE_NATIVE_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_NATIVE_ARCHITECTURE' as const

export const LOGRES_GLOBAL_3024_RESULT_DISPLAY_MODES =
  Object.freeze([
    1,
    2,
  ] as const)

export type LogresGlobal3024ResultDisplayMode =
  typeof LOGRES_GLOBAL_3024_RESULT_DISPLAY_MODES[number]

export type LogresGlobal3024SequencedEventType =
  | 'CHARGE_SKILL'
  | 'CANCEL_CHARGE'
  | 'FAILED_CHARGE'
  | 'EXECUTE_SKILL'
  | 'WAIT_SKILL'
  | 'RECAST_SKILL'
  | 'RESET_RECAST_SKILL'
  | 'SEAL_SKILL'
  | 'SELECT_REACTION_SKILL'
  | 'EXECUTE_REACTION_SKILL'
  | 'CHAR_TARGET_LOCK'
  | 'CHAR_TARGET_UNLOCK'
  | 'STATUS_CHANGED'
  | 'ADD_ENCHANT'
  | 'REMOVE_ENCHANT'
  | 'EFFECT_GENERATED'
  | 'DEAD'
  | 'REVIVE'
  | 'DROP'
  | 'GENERATE_GAUGE'
  | 'UPDATE_GAUGE'
  | 'DELETE_GAUGE'
  | 'BOUT_RESULT'
  | 'BOUT_FINISH'

export interface LogresGlobal3024CommandSkillIntent {
  readonly actorRef: string
  readonly itemRef: string
  readonly skillRef: string
  readonly targetRef: string
}

export interface LogresGlobal3024SkillRequestResponse {
  readonly rawCode0: number
  readonly rawCode1: number
  readonly responseInfoRef:
    | string
    | null
}

export interface LogresGlobal3024SequencedEvent {
  readonly sequenceRef: string
  readonly ordinal: number
  readonly type:
    LogresGlobal3024SequencedEventType
  readonly actorRef:
    | string
    | null
  readonly targetRef:
    | string
    | null
  readonly skillRef:
    | string
    | null
  readonly payloadRef:
    | string
    | null
}

export interface LogresGlobal3024BattleNativeSnapshot {
  readonly provenance:
    typeof LOGRES_GLOBAL_3024_BATTLE_NATIVE_PROVENANCE
  readonly source:
    typeof LOGRES_GLOBAL_3024_BATTLE_SOURCE
  readonly authorityModel:
    typeof LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE.authorityModel
  readonly battleSystemRef:
    | string
    | null
  readonly boutSystemRef:
    | string
    | null
  readonly activeSequenceRef:
    | string
    | null
  readonly clientSkillIntents:
    readonly Readonly<LogresGlobal3024CommandSkillIntent>[]
  readonly skillRequestResponses:
    readonly Readonly<LogresGlobal3024SkillRequestResponse>[]
  readonly serverEvents:
    readonly Readonly<LogresGlobal3024SequencedEvent>[]
  readonly targetLocks:
    Readonly<Record<string, string>>
  readonly resultReceived: boolean
  readonly boutFinished: boolean
  readonly resultPresented: boolean
  readonly resultDisplayMode:
    | LogresGlobal3024ResultDisplayMode
    | null
  readonly finishFlowRequested: boolean
  readonly finishFlowFlag:
    | boolean
    | null
}

function requiredRef(
  value: string,
  label: string,
): string {
  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      `${label} must be non-empty`,
    )
  }

  return normalized
}

function optionalRef(
  value:
    | string
    | null
    | undefined,
  label: string,
): string | null {
  if (
    value ===
      null ||
    value ===
      undefined
  ) {
    return null
  }

  return requiredRef(
    value,
    label,
  )
}

function requiredSafeInteger(
  value: number,
  label: string,
): number {
  if (
    !Number.isSafeInteger(
      value,
    )
  ) {
    throw new Error(
      `${label} must be a safe integer`,
    )
  }

  return value
}

/**
 * Client-side projection of the signed Global 3.0.24 battle authority boundary.
 *
 * Confirmed native architecture:
 * - BattleSystem owns the top-level battle lifecycle.
 * - BoutSystem owns the active bout.
 * - BoutSequencer receives and orders server-authored battle events.
 * - requestToUseCommandSkill creates client intent; EXECUTE_SKILL is a later
 *   server-authored sequenced event.
 * - target locks, gauges, status, death/drop/result are server projections.
 *
 * This class deliberately does not calculate damage, cooldowns, EP costs,
 * enemy stats, or reward rolls. Those remain server-side/unresolved.
 */
export class LogresGlobal3024BattleNativeAuthority {
  private battleSystemRef:
    | string
    | null =
      null

  private boutSystemRef:
    | string
    | null =
      null

  private activeSequenceRef:
    | string
    | null =
      null

  private readonly clientSkillIntents:
    Readonly<LogresGlobal3024CommandSkillIntent>[] =
      []

  private readonly skillRequestResponses:
    Readonly<LogresGlobal3024SkillRequestResponse>[] =
      []

  private readonly serverEvents:
    Readonly<LogresGlobal3024SequencedEvent>[] =
      []

  private readonly targetLocks =
    new Map<string, string>()

  private resultReceived =
    false

  private boutFinished =
    false

  private resultPresented =
    false

  private resultDisplayMode:
    | LogresGlobal3024ResultDisplayMode
    | null =
      null

  private finishFlowRequested =
    false

  private finishFlowFlag:
    | boolean
    | null =
      null

  initializeBattle(
    battleSystemRef: string,
  ): void {
    if (
      this.battleSystemRef !==
      null
    ) {
      throw new Error(
        'Global BattleSystem is already initialized',
      )
    }

    this.battleSystemRef =
      requiredRef(
        battleSystemRef,
        'BattleSystem ref',
      )
  }

  initializeBout(
    boutSystemRef: string,
  ): void {
    this.requireBattle()

    if (
      this.boutSystemRef !==
      null &&
      !this.boutFinished
    ) {
      throw new Error(
        'Global BoutSystem is already active',
      )
    }

    this.boutSystemRef =
      requiredRef(
        boutSystemRef,
        'BoutSystem ref',
      )

    this.activeSequenceRef =
      null
    this.resultReceived =
      false
    this.boutFinished =
      false
    this.resultPresented =
      false
    this.resultDisplayMode =
      null
    this.finishFlowRequested =
      false
    this.finishFlowFlag =
      null
    this.targetLocks.clear()
  }

  beginSequence(
    sequenceRef: string,
  ): void {
    this.requireBout()

    if (
      this.activeSequenceRef !==
      null
    ) {
      throw new Error(
        'Global BoutSequencer sequence is already active',
      )
    }

    this.activeSequenceRef =
      requiredRef(
        sequenceRef,
        'Bout event sequence ref',
      )
  }

  endSequence(
    sequenceRef: string,
  ): void {
    const active =
      this.requireActiveSequence()

    const normalized =
      requiredRef(
        sequenceRef,
        'Bout event sequence ref',
      )

    if (
      normalized !==
      active
    ) {
      throw new Error(
        'Bout event sequence end does not match the active sequence',
      )
    }

    this.activeSequenceRef =
      null
  }

  requestCommandSkill(
    input:
      LogresGlobal3024CommandSkillIntent,
  ): Readonly<LogresGlobal3024CommandSkillIntent> {
    this.requireBout()

    if (
      this.boutFinished
    ) {
      throw new Error(
        'Cannot request a command skill after bout finish',
      )
    }

    const intent =
      Object.freeze({
        actorRef:
          requiredRef(
            input.actorRef,
            'Command skill actor ref',
          ),
        itemRef:
          requiredRef(
            input.itemRef,
            'Command skill item ref',
          ),
        skillRef:
          requiredRef(
            input.skillRef,
            'Command skill ref',
          ),
        targetRef:
          requiredRef(
            input.targetRef,
            'Command skill target ref',
          ),
      })

    this.clientSkillIntents.push(
      intent,
    )

    return intent
  }

  recordCommandSkillResponse(
    input: {
      rawCode0: number
      rawCode1: number
      responseInfoRef?:
        | string
        | null
    },
  ): Readonly<LogresGlobal3024SkillRequestResponse> {
    this.requireBout()

    const response =
      Object.freeze({
        rawCode0:
          requiredSafeInteger(
            input.rawCode0,
            'Skill response rawCode0',
          ),
        rawCode1:
          requiredSafeInteger(
            input.rawCode1,
            'Skill response rawCode1',
          ),
        responseInfoRef:
          optionalRef(
            input.responseInfoRef,
            'Skill response info ref',
          ),
      })

    this.skillRequestResponses.push(
      response,
    )

    return response
  }

  receiveSequencedEvent(
    input: {
      type:
        LogresGlobal3024SequencedEventType
      actorRef?:
        | string
        | null
      targetRef?:
        | string
        | null
      skillRef?:
        | string
        | null
      payloadRef?:
        | string
        | null
    },
  ): Readonly<LogresGlobal3024SequencedEvent> {
    const sequenceRef =
      this.requireActiveSequence()

    const event =
      Object.freeze({
        sequenceRef,
        ordinal:
          this.serverEvents.length,
        type:
          input.type,
        actorRef:
          optionalRef(
            input.actorRef,
            'Battle event actor ref',
          ),
        targetRef:
          optionalRef(
            input.targetRef,
            'Battle event target ref',
          ),
        skillRef:
          optionalRef(
            input.skillRef,
            'Battle event skill ref',
          ),
        payloadRef:
          optionalRef(
            input.payloadRef,
            'Battle event payload ref',
          ),
      })

    switch (
      event.type
    ) {
      case 'CHAR_TARGET_LOCK': {
        if (
          event.actorRef ===
            null ||
          event.targetRef ===
            null
        ) {
          throw new Error(
            'CHAR_TARGET_LOCK requires actor and target refs',
          )
        }

        this.targetLocks.set(
          event.actorRef,
          event.targetRef,
        )

        break
      }

      case 'CHAR_TARGET_UNLOCK': {
        if (
          event.actorRef ===
          null
        ) {
          throw new Error(
            'CHAR_TARGET_UNLOCK requires an actor ref',
          )
        }

        this.targetLocks.delete(
          event.actorRef,
        )

        break
      }

      case 'BOUT_RESULT': {
        this.resultReceived =
          true

        break
      }

      case 'BOUT_FINISH': {
        this.boutFinished =
          true

        break
      }

      default:
        break
    }

    this.serverEvents.push(
      event,
    )

    return event
  }

  displayResult(
    input: {
      displayMode:
        LogresGlobal3024ResultDisplayMode
      resultPayloadRef: string
    },
  ): void {
    this.requireBattle()

    if (
      !LOGRES_GLOBAL_3024_RESULT_DISPLAY_MODES.includes(
        input.displayMode,
      )
    ) {
      throw new Error(
        'Global 3.0.24 result display mode must be 1 or 2',
      )
    }

    requiredRef(
      input.resultPayloadRef,
      'Battle result payload ref',
    )

    /*
     * Signed Global 3.0.24 BattleSystem::displayResult branches only on
     * raw mode 1 or 2 after validating the BattleSystem UID. The function
     * itself does not require a locally observed BOUT_RESULT flag.
     */
    this.resultPresented =
      true
    this.resultDisplayMode =
      input.displayMode
  }

  requestFinishFlow(
    finishFlag: boolean,
  ): void {
    this.requireBout()

    /*
     * Signed Global 3.0.24 BoutSystem::goToFinishFlow(bool) stores the
     * supplied boolean and marks the finish-flow state directly. The
     * function body itself does not guard on an observed BOUT_FINISH event.
     */
    this.finishFlowRequested =
      true
    this.finishFlowFlag =
      finishFlag
  }

  snapshot():
    Readonly<LogresGlobal3024BattleNativeSnapshot> {
    return Object.freeze({
      provenance:
        LOGRES_GLOBAL_3024_BATTLE_NATIVE_PROVENANCE,
      source:
        LOGRES_GLOBAL_3024_BATTLE_SOURCE,
      authorityModel:
        LOGRES_GLOBAL_3024_BATTLE_ARCHITECTURE
          .authorityModel,
      battleSystemRef:
        this.battleSystemRef,
      boutSystemRef:
        this.boutSystemRef,
      activeSequenceRef:
        this.activeSequenceRef,
      clientSkillIntents:
        Object.freeze([
          ...this.clientSkillIntents,
        ]),
      skillRequestResponses:
        Object.freeze([
          ...this.skillRequestResponses,
        ]),
      serverEvents:
        Object.freeze([
          ...this.serverEvents,
        ]),
      targetLocks:
        Object.freeze(
          Object.fromEntries(
            this.targetLocks,
          ),
        ),
      resultReceived:
        this.resultReceived,
      boutFinished:
        this.boutFinished,
      resultPresented:
        this.resultPresented,
      resultDisplayMode:
        this.resultDisplayMode,
      finishFlowRequested:
        this.finishFlowRequested,
      finishFlowFlag:
        this.finishFlowFlag,
    })
  }

  private requireBattle():
    string {
    if (
      this.battleSystemRef ===
      null
    ) {
      throw new Error(
        'Global BattleSystem is not initialized',
      )
    }

    return this.battleSystemRef
  }

  private requireBout():
    string {
    this.requireBattle()

    if (
      this.boutSystemRef ===
      null
    ) {
      throw new Error(
        'Global BoutSystem is not initialized',
      )
    }

    return this.boutSystemRef
  }

  private requireActiveSequence():
    string {
    this.requireBout()

    if (
      this.activeSequenceRef ===
      null
    ) {
      throw new Error(
        'Global BoutSequencer has no active sequence',
      )
    }

    return this.activeSequenceRef
  }
}
