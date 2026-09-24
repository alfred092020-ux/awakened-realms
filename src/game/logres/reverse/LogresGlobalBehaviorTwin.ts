export type LogresGlobalBehaviorState =
  | 'TITLE'
  | 'ACCOUNT_AUTH'
  | 'TERMS_GATE'
  | 'CHARACTER_LIST'
  | 'PREBEGIN_INIT'
  | 'GENDER_CREATE'
  | 'CHARACTER_LOGIN'
  | 'ERROR_OR_EXTERNAL_AUTHORITY'
  | 'FIELD_SELECT'
  | 'FIELD_INFO'
  | 'ZONEIN'
  | 'AREA_ACTIVE'
  | 'FIELD_MOVEMENT'
  | 'NPC_INTERACTION'
  | 'ENCOUNTER_ELIGIBILITY'
  | 'BATTLE_ENTRY_PENDING'
  | 'BATTLE_ACCEPTED'
  | 'BATTLE_ENTRY_RETRY_WAIT'
  | 'BATTLE_INITIALIZING'
  | 'BOUT_ACTIVE'
  | 'BATTLE_RESULT'
  | 'REWARD_PROJECTION'
  | 'FIELD_RETURN'

export type BehaviorAuthority =
  | 'GLOBAL_CLIENT_DIRECT'
  | 'GLOBAL_CLIENT_PROTOCOL_PROJECTION'
  | 'SERVER_AUTHORITY_STUB'

export interface ServerAuthorityStub<T> {
  readonly kind: 'SERVER_AUTHORITY_STUB'
  readonly value: T
  readonly evidenceCeiling: string
}

export function serverAuthorityStub<T>(
  value: T,
  evidenceCeiling: string,
): ServerAuthorityStub<T> {
  return Object.freeze({
    kind: 'SERVER_AUTHORITY_STUB' as const,
    value,
    evidenceCeiling,
  })
}

export interface BehaviorTransitionDefinition {
  readonly id: number
  readonly from: LogresGlobalBehaviorState
  readonly to: LogresGlobalBehaviorState
  readonly event: string
  readonly message?: string
  readonly guard?: string
  readonly action?: string
  readonly provenance: string
  readonly authority: BehaviorAuthority
  readonly serverAuthority: boolean
}

export interface BehaviorTraceStep extends BehaviorTransitionDefinition {
  readonly sequence: number
  readonly stubEvidenceCeiling?: string
}

export class EvidenceExceededError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'EvidenceExceededError'
  }
}

export const GLOBAL_BEHAVIOR_TRANSITIONS: readonly BehaviorTransitionDefinition[] =
  Object.freeze([
    {
      id: 0,
      from: 'TITLE',
      to: 'ACCOUNT_AUTH',
      event: 'TAP_START',
      provenance: 'GLOBAL_NATIVE_SCENE_AND_AUTH_SYMBOL_SURFACE',
      authority: 'GLOBAL_CLIENT_DIRECT',
      serverAuthority: false,
    },
    {
      id: 1,
      from: 'ACCOUNT_AUTH',
      to: 'TERMS_GATE',
      event: 'ACCOUNT_LOGIN_NOT_AGREED',
      message: 'C_GMCL_ACCOUNT_LOGIN_REQ_Response',
      guard: 'AccountLoginResult=3',
      action: 'ReleaseScene_AccountLogIn::onAuthRequireAgreement creates AgreementWebView',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x0205ed78',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 2,
      from: 'ACCOUNT_AUTH',
      to: 'CHARACTER_LIST',
      event: 'ACCOUNT_LOGIN_ACCEPTED',
      message: 'C_GMCL_ACCOUNT_LOGIN_REQ_Response',
      guard: 'SUCCESS=1 or REAUTH_SUCCESS=2',
      provenance: 'GLOBAL_PROTOCOL_ENUM_PLUS_AUTHENTICATION_BEHAVIOR',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 3,
      from: 'CHARACTER_LIST',
      to: 'PREBEGIN_INIT',
      event: 'CHARACTER_LIST_CALLBACK',
      action: 'branch=1 empty, branch=2 non-empty; initializeForPreBeginGame',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x0205f024',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 4,
      from: 'PREBEGIN_INIT',
      to: 'GENDER_CREATE',
      event: 'PREBEGIN_BRANCH_1',
      action: 'ReleaseScene_CharcterMake::create',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478440',
      authority: 'GLOBAL_CLIENT_DIRECT',
      serverAuthority: false,
    },
    {
      id: 5,
      from: 'PREBEGIN_INIT',
      to: 'CHARACTER_LOGIN',
      event: 'PREBEGIN_BRANCH_2',
      action: 'ReleaseScene_CharacterLogin::create',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478400',
      authority: 'GLOBAL_CLIENT_DIRECT',
      serverAuthority: false,
    },
    {
      id: 6,
      from: 'PREBEGIN_INIT',
      to: 'TITLE',
      event: 'PREBEGIN_BRANCH_4',
      action: 'ReleaseScene_Title::create',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x0205f4a0_PLUS_PLT_0x1478450',
      authority: 'GLOBAL_CLIENT_DIRECT',
      serverAuthority: false,
    },
    {
      id: 7,
      from: 'GENDER_CREATE',
      to: 'CHARACTER_LOGIN',
      event: 'CHARACTER_CREATE_SUCCESS',
      message: 'C_GMCL_CHAR_CREATE_REQ_Response',
      guard: 'e_GmClCharCreateResult::SUCCESS=0',
      action: 'SceneManager::changeScene(ReleaseScene_CharacterLogin::create())',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x02069078_PLUS_PLT_0x1478400',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 8,
      from: 'CHARACTER_LOGIN',
      to: 'PREBEGIN_INIT',
      event: 'CHARACTER_LOGIN_ACCEPTED',
      message: 'C_GMCL_CHAR_LOGIN_REQ_Response',
      guard: 'reply code in {1,2,3,4}',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01e9d644',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 9,
      from: 'CHARACTER_LOGIN',
      to: 'ERROR_OR_EXTERNAL_AUTHORITY',
      event: 'CHARACTER_LOGIN_ERROR',
      message: 'C_GMCL_CHAR_LOGIN_REQ_Response',
      guard: 'reply code outside 1..4',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01e9d644',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 10,
      from: 'PREBEGIN_INIT',
      to: 'FIELD_SELECT',
      event: 'BEGIN_FIELD_BOOTSTRAP',
      message: 'C_GMCL_FIELD_SELECT_REQ',
      provenance: 'GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 11,
      from: 'FIELD_SELECT',
      to: 'FIELD_INFO',
      event: 'SERVER_FIELD_SELECT',
      message: 'S_GMCL_FIELD_SELECT_REQ',
      provenance: 'GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 12,
      from: 'FIELD_INFO',
      to: 'ZONEIN',
      event: 'ZONE_IN_REQUEST',
      message: 'C_GMCL_ZONEIN_REQ',
      provenance: 'GLOBAL_PROTOCOL_SURFACE_AND_FIELD_NATIVE_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 13,
      from: 'ZONEIN',
      to: 'AREA_ACTIVE',
      event: 'SERVER_AREA_ENTER',
      message: 'S_GMCL_AREA_ENTER',
      action: 'construct AreaEnter and publish NetworkManager event',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01eb7590',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 14,
      from: 'AREA_ACTIVE',
      to: 'FIELD_MOVEMENT',
      event: 'LOCAL_MOVE_REQUEST',
      message: 'C_GMCL_CHAR_MOVE_REQ',
      action: 'SimpleAStar -> MovePathInitializer -> MoverComplyPath',
      provenance: 'GLOBAL_NATIVE_FIELD_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 15,
      from: 'AREA_ACTIVE',
      to: 'NPC_INTERACTION',
      event: 'NPC_TALK_REQUEST',
      message: 'C_GMCL_CHAR_TALK_REQ',
      provenance: 'GLOBAL_NATIVE_FIELD_AND_NPC_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 16,
      from: 'AREA_ACTIVE',
      to: 'ENCOUNTER_ELIGIBILITY',
      event: 'SERVER_ENEMY_APPEAR',
      message: 'S_GMCL_ENEMY_APPEAR',
      provenance: 'GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 17,
      from: 'ENCOUNTER_ELIGIBILITY',
      to: 'BATTLE_ENTRY_PENDING',
      event: 'BATTLE_ENTRY_REQUEST',
      message: 'C_GMCL_BATTLE_ENTRY_REQ',
      provenance: 'GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 18,
      from: 'BATTLE_ENTRY_PENDING',
      to: 'BATTLE_ACCEPTED',
      event: 'BATTLE_ENTRY_ACCEPTED',
      message: 'C_GMCL_BATTLE_ENTRY_REQ_Response',
      guard: 'response code=1',
      action: 'entryAccepted=true',
      provenance:
        'GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 19,
      from: 'BATTLE_ENTRY_PENDING',
      to: 'BATTLE_ENTRY_RETRY_WAIT',
      event: 'BATTLE_ENTRY_RETRY',
      message: 'C_GMCL_BATTLE_ENTRY_REQ_Response',
      guard: 'response code=2',
      action: 'retry wait exactly 1.0 second',
      provenance:
        'GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE_PLUS_GLOBAL_HANDLER_0x01eba148',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 20,
      from: 'BATTLE_ENTRY_RETRY_WAIT',
      to: 'BATTLE_ENTRY_PENDING',
      event: 'BATTLE_RETRY_DELAY_ELAPSED',
      message: 'C_GMCL_BATTLE_ENTRY_REQ',
      guard: 'elapsed seconds=1.0',
      provenance: 'GLOBAL_DIRECT_ENCOUNTER_NATIVE_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 21,
      from: 'BATTLE_ACCEPTED',
      to: 'BATTLE_INITIALIZING',
      event: 'SERVER_BATTLE_INITIALIZE',
      message: 'S_GMCL_BATTLE_INITIALIZE',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01ebaec0',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 22,
      from: 'BATTLE_INITIALIZING',
      to: 'BOUT_ACTIVE',
      event: 'SERVER_BOUT_INITIALIZE',
      message: 'S_GMCL_BATTLE_BOUT_INITIALIZE',
      provenance: 'GLOBAL_NATIVE_BATTLE_ARCHITECTURE',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 23,
      from: 'BOUT_ACTIVE',
      to: 'BOUT_ACTIVE',
      event: 'USE_SKILL_REQUEST',
      message: 'C_GMCL_BATTLE_USE_SKILL_REQ',
      provenance: 'GLOBAL_PROTOCOL_AND_BATTLE_NATIVE_EVIDENCE',
      authority: 'GLOBAL_CLIENT_PROTOCOL_PROJECTION',
      serverAuthority: false,
    },
    {
      id: 24,
      from: 'BOUT_ACTIVE',
      to: 'BATTLE_RESULT',
      event: 'SERVER_BATTLE_RESULT',
      message: 'S_GMCL_BATTLE_RESULT',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01ebb04c',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 25,
      from: 'BATTLE_RESULT',
      to: 'REWARD_PROJECTION',
      event: 'SERVER_QUEST_RESULT',
      message: 'S_GMCL_QUEST_INFO_STATE_RESULT',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01ec21c4_PLUS_GLOBAL_BATTLE_EVIDENCE',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 26,
      from: 'REWARD_PROJECTION',
      to: 'FIELD_RETURN',
      event: 'SERVER_QUEST_RETURN',
      message: 'S_GMCL_QUEST_INFO_STATE_RETURN',
      provenance: 'GLOBAL_DIRECT_GHIDRA_0x01ec263c',
      authority: 'SERVER_AUTHORITY_STUB',
      serverAuthority: true,
    },
    {
      id: 27,
      from: 'FIELD_RETURN',
      to: 'AREA_ACTIVE',
      event: 'RESUME_FIELD_RUNTIME',
      provenance: 'GLOBAL_NATIVE_BATTLE_AND_FIELD_EVIDENCE',
      authority: 'GLOBAL_CLIENT_DIRECT',
      serverAuthority: false,
    },
  ] as const)

const TRANSITION_BY_ID: ReadonlyMap<number, BehaviorTransitionDefinition> = new Map(
  GLOBAL_BEHAVIOR_TRANSITIONS.map((transition) => [transition.id, transition]),
)

export interface BehaviorTwinOptions {
  readonly initialState?: LogresGlobalBehaviorState
}

export class LogresGlobalBehaviorTwin {
  private _state: LogresGlobalBehaviorState
  private _trace: BehaviorTraceStep[] = []
  private prebeginBranch: 1 | 2 | 3 | 4 | null = null

  constructor(options: BehaviorTwinOptions = {}) {
    this._state = options.initialState ?? 'TITLE'
  }

  get state(): LogresGlobalBehaviorState {
    return this._state
  }

  get trace(): readonly BehaviorTraceStep[] {
    return this._trace
  }

  private apply(id: number, stub?: ServerAuthorityStub<unknown>): void {
    const transition = TRANSITION_BY_ID.get(id)
    if (!transition) throw new EvidenceExceededError(`Unknown transition ${id}`)
    if (transition.from !== this._state) {
      throw new EvidenceExceededError(
        `Transition ${id} requires ${transition.from}, current=${this._state}`,
      )
    }
    if (transition.serverAuthority && !stub) {
      throw new EvidenceExceededError(
        `Transition ${id} requires an explicit SERVER_AUTHORITY_STUB`,
      )
    }
    this._state = transition.to
    this._trace.push(
      Object.freeze({
        ...transition,
        sequence: this._trace.length,
        stubEvidenceCeiling: stub?.evidenceCeiling,
      }),
    )
  }

  tapStart(): void {
    this.apply(0)
  }

  receiveAccountLogin(result: ServerAuthorityStub<number>): void {
    if (result.value === 3) return this.apply(1, result)
    if (result.value === 1 || result.value === 2) return this.apply(2, result)
    throw new EvidenceExceededError(
      `Account-login result ${result.value} has no modeled critical-loop transition`,
    )
  }

  receiveCharacterList(result: ServerAuthorityStub<{ count: number }>): void {
    this.prebeginBranch = result.value.count === 0 ? 1 : 2
    this.apply(3, result)
  }

  resolvePrebeginBranch(): void {
    if (this.prebeginBranch === 1) return this.apply(4)
    if (this.prebeginBranch === 2) return this.apply(5)
    if (this.prebeginBranch === 4) return this.apply(6)
    throw new EvidenceExceededError(
      'Prebegin branch 3 has no direct recovered scene factory; stopping at evidence ceiling',
    )
  }

  setTitleFallbackBranchForTest(): void {
    this.prebeginBranch = 4
  }

  receiveCharacterCreate(result: ServerAuthorityStub<number>): void {
    if (result.value === 0) return this.apply(7, result)
    throw new EvidenceExceededError(
      `Character-create code ${result.value} does not advance the recovered success path`,
    )
  }

  receiveCharacterLogin(result: ServerAuthorityStub<number>): void {
    if ([1, 2, 3, 4].includes(result.value)) return this.apply(8, result)
    this.apply(9, result)
  }

  beginFieldBootstrap(): void {
    this.apply(10)
  }

  receiveFieldSelect(stub: ServerAuthorityStub<unknown>): void {
    this.apply(11, stub)
  }

  requestZoneIn(): void {
    this.apply(12)
  }

  receiveAreaEnter(stub: ServerAuthorityStub<unknown>): void {
    this.apply(13, stub)
  }

  requestMove(): void {
    this.apply(14)
  }

  requestNpcTalk(): void {
    this.apply(15)
  }

  receiveEnemyAppear(stub: ServerAuthorityStub<unknown>): void {
    this.apply(16, stub)
  }

  requestBattleEntry(): void {
    this.apply(17)
  }

  receiveBattleEntry(result: ServerAuthorityStub<number>): void {
    if (result.value === 1) return this.apply(18, result)
    if (result.value === 2) return this.apply(19, result)
    throw new EvidenceExceededError(
      `Battle-entry response ${result.value} is outside recovered codes 1/2`,
    )
  }

  elapseBattleRetry(seconds: number): void {
    if (seconds !== 1) {
      throw new EvidenceExceededError(
        `Recovered retry delay is exactly 1.0 second, got ${seconds}`,
      )
    }
    this.apply(20)
  }

  receiveBattleInitialize(stub: ServerAuthorityStub<unknown>): void {
    this.apply(21, stub)
  }

  receiveBoutInitialize(stub: ServerAuthorityStub<unknown>): void {
    this.apply(22, stub)
  }

  requestUseSkill(): void {
    this.apply(23)
  }

  receiveBattleResult(stub: ServerAuthorityStub<unknown>): void {
    this.apply(24, stub)
  }

  receiveQuestResult(stub: ServerAuthorityStub<unknown>): void {
    this.apply(25, stub)
  }

  receiveQuestReturn(stub: ServerAuthorityStub<unknown>): void {
    this.apply(26, stub)
  }

  resumeField(): void {
    this.apply(27)
  }
}

export interface ImplementationTraceStep {
  readonly from: LogresGlobalBehaviorState
  readonly to: LogresGlobalBehaviorState
  readonly message?: string
  readonly event?: string
  readonly serverAuthorityClaim?:
    | 'SERVER_STUB'
    | 'CLIENT_PROJECTION'
    | 'CONFIRMED_RETIRED_SERVER'
}

export interface TraceComparison {
  readonly pass: boolean
  readonly mismatches: readonly string[]
}

export function compareBehaviorTrace(
  expected: readonly BehaviorTraceStep[],
  actual: readonly ImplementationTraceStep[],
): TraceComparison {
  const mismatches: string[] = []
  const length = Math.max(expected.length, actual.length)
  for (let index = 0; index < length; index += 1) {
    const exp = expected[index]
    const got = actual[index]
    if (!exp || !got) {
      mismatches.push(`step ${index}: trace length mismatch`)
      continue
    }
    if (exp.from !== got.from || exp.to !== got.to) {
      mismatches.push(
        `step ${index}: expected ${exp.from}->${exp.to}, got ${got.from}->${got.to}`,
      )
    }
    if ((exp.message ?? null) !== (got.message ?? null)) {
      mismatches.push(
        `step ${index}: expected message ${exp.message ?? 'none'}, got ${got.message ?? 'none'}`,
      )
    }
  }
  return Object.freeze({ pass: mismatches.length === 0, mismatches })
}

export function assertImplementationWithinEvidence(
  actual: readonly ImplementationTraceStep[],
): void {
  for (const [index, step] of actual.entries()) {
    const matching = GLOBAL_BEHAVIOR_TRANSITIONS.filter(
      (transition) =>
        transition.from === step.from &&
        transition.to === step.to &&
        (transition.message ?? null) === (step.message ?? null),
    )
    if (matching.length === 0) {
      throw new EvidenceExceededError(
        `Implementation step ${index} is not in recovered Global transition evidence: ${step.from}->${step.to}`,
      )
    }
    if (
      matching.some((transition) => transition.serverAuthority) &&
      step.serverAuthorityClaim === 'CONFIRMED_RETIRED_SERVER'
    ) {
      throw new EvidenceExceededError(
        `Implementation step ${index} promotes retired-server authority beyond evidence`,
      )
    }
  }
}
