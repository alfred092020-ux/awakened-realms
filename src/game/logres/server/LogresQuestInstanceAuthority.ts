export const LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE =
  'RECONSTRUCTED' as const

export interface LogresQuestSpawnCoord {
  col: number
  row: number
}

export interface LogresQuestRules {
  timeLimitSeconds:
    | number
    | null
  defeatLimit:
    | number
    | null
  battleCapacity:
    | number
    | null
  requiredPower:
    | number
    | null
}

export interface ReconstructedLogresQuestInstanceInput {
  /**
   * Reconstruction-local stable identity.
   *
   * This is not claimed to be an original quest/server identifier.
   */
  instanceKey: string

  /**
   * Original identifiers remain nullable until recovered.
   */
  questRecordId:
    | string
    | null
  mapId:
    | string
    | null
  roomId:
    | string
    | null

  playerSpawn:
    | LogresQuestSpawnCoord
    | null

  objectiveIds:
    readonly string[]
  encounterIds:
    readonly string[]
  npcStateIds:
    readonly string[]
  tutorialOverlayIds:
    readonly string[]

  rules:
    LogresQuestRules
}

export interface ReconstructedLogresQuestInstance
  extends ReconstructedLogresQuestInstanceInput {
  provenance:
    typeof LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE
}

const MAP_ID_PATTERN =
  /^\d{3}_\d{3}_\d{5}$/

function requireNonEmptyLocalKey(
  value: string,
): string {
  const normalized =
    value.trim()

  if (!normalized) {
    throw new Error(
      'Quest instanceKey must be non-empty',
    )
  }

  return normalized
}

function requireOptionalString(
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

function requireOptionalNonNegativeInteger(
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
    ) ||
    value < 0
  ) {
    throw new Error(
      `${label} must be null or a non-negative safe integer`,
    )
  }

  return value
}

function requireOptionalPositiveInteger(
  value:
    | number
    | null,
  label: string,
): number | null {
  const normalized =
    requireOptionalNonNegativeInteger(
      value,
      label,
    )

  if (
    normalized !== null &&
    normalized === 0
  ) {
    throw new Error(
      `${label} must be null or a positive safe integer`,
    )
  }

  return normalized
}

function freezeStringList(
  values:
    readonly string[],
  label: string,
): readonly string[] {
  const seen =
    new Set<string>()

  const normalized =
    values.map(
      (value) => {
        const item =
          value.trim()

        if (!item) {
          throw new Error(
            `${label} entries must be non-empty`,
          )
        }

        if (
          seen.has(
            item,
          )
        ) {
          throw new Error(
            `${label} entries must be unique`,
          )
        }

        seen.add(
          item,
        )

        return item
      },
    )

  return Object.freeze(
    normalized,
  )
}

function normalizeSpawn(
  spawn:
    | LogresQuestSpawnCoord
    | null,
):
  | Readonly<LogresQuestSpawnCoord>
  | null {
  if (spawn === null) {
    return null
  }

  if (
    !Number.isSafeInteger(
      spawn.col,
    ) ||
    !Number.isSafeInteger(
      spawn.row,
    )
  ) {
    throw new Error(
      'Quest playerSpawn coordinates must be safe integers',
    )
  }

  return Object.freeze({
    col:
      spawn.col,
    row:
      spawn.row,
  })
}

/**
 * Creates a replacement-server quest-instance snapshot without inventing
 * historical values.
 *
 * RECONSTRUCTED contract:
 * - map identity is independent from Room/quest state
 * - spawn, objectives, encounters, NPC state, overlays, and rule limits are
 *   explicit instance data
 * - unknown original values stay null/empty rather than receiving defaults
 *
 * This is an authority/data boundary only. It does not claim the original
 * server packet schema.
 */
export function createReconstructedLogresQuestInstance(
  input:
    ReconstructedLogresQuestInstanceInput,
): Readonly<ReconstructedLogresQuestInstance> {
  const mapId =
    requireOptionalString(
      input.mapId,
      'Quest mapId',
    )

  if (
    mapId !== null &&
    !MAP_ID_PATTERN.test(
      mapId,
    )
  ) {
    throw new Error(
      'Quest mapId must be null or a canonical ###_###_##### map id',
    )
  }

  const rules =
    Object.freeze({
      timeLimitSeconds:
        requireOptionalNonNegativeInteger(
          input.rules
            .timeLimitSeconds,
          'Quest timeLimitSeconds',
        ),
      defeatLimit:
        requireOptionalNonNegativeInteger(
          input.rules
            .defeatLimit,
          'Quest defeatLimit',
        ),
      battleCapacity:
        requireOptionalPositiveInteger(
          input.rules
            .battleCapacity,
          'Quest battleCapacity',
        ),
      requiredPower:
        requireOptionalNonNegativeInteger(
          input.rules
            .requiredPower,
          'Quest requiredPower',
        ),
    })

  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
    instanceKey:
      requireNonEmptyLocalKey(
        input.instanceKey,
      ),
    questRecordId:
      requireOptionalString(
        input.questRecordId,
        'Quest questRecordId',
      ),
    mapId,
    roomId:
      requireOptionalString(
        input.roomId,
        'Quest roomId',
      ),
    playerSpawn:
      normalizeSpawn(
        input.playerSpawn,
      ),
    objectiveIds:
      freezeStringList(
        input.objectiveIds,
        'Quest objectiveIds',
      ),
    encounterIds:
      freezeStringList(
        input.encounterIds,
        'Quest encounterIds',
      ),
    npcStateIds:
      freezeStringList(
        input.npcStateIds,
        'Quest npcStateIds',
      ),
    tutorialOverlayIds:
      freezeStringList(
        input.tutorialOverlayIds,
        'Quest tutorialOverlayIds',
      ),
    rules,
  })
}

/**
 * Critical-path starting point for the opening tutorial while historical
 * server values remain unresolved.
 *
 * The local key is RECONSTRUCTED. Every original identifier and rule value is
 * intentionally unresolved.
 */
export function createUnresolvedTutorialQuestInstance():
  Readonly<ReconstructedLogresQuestInstance> {
  return (
    createReconstructedLogresQuestInstance({
      instanceKey:
        'opening-tutorial',
      questRecordId:
        null,
      mapId:
        null,
      roomId:
        null,
      playerSpawn:
        null,
      objectiveIds:
        [],
      encounterIds:
        [],
      npcStateIds:
        [],
      tutorialOverlayIds:
        [],
      rules: {
        timeLimitSeconds:
          null,
        defeatLimit:
          null,
        battleCapacity:
          null,
        requiredPower:
          null,
      },
    })
  )
}

export type ReconstructedLogresQuestFlowPhase =
  | 'issued'
  | 'accepted'
  | 'in-progress'
  | 'completed'
  | 'reward-granted'

export interface ReconstructedLogresQuestAuthenticator {
  actorRef: string
  sessionToken: string
}

export interface ReconstructedLogresQuestFlowState {
  provenance:
    typeof LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE
  revision: number
  instance:
    Readonly<ReconstructedLogresQuestInstance>
  phase:
    ReconstructedLogresQuestFlowPhase
  authenticatedActorRef: string
  authenticatedSessionToken: string
  originalQuestUid:
    | string
    | null
  progressKeys:
    readonly string[]
  appliedProgressRequestIds:
    readonly string[]
  acceptRequestId:
    | string
    | null
  completionRequestId:
    | string
    | null
  rewardGrantKey:
    | string
    | null
  originalCompletionRef:
    | string
    | null
  originalRewardRef:
    | string
    | null
}

export interface ReconstructedLogresQuestFlowApplyResult {
  applied: boolean
  state:
    Readonly<ReconstructedLogresQuestFlowState>
}

function requireAuthenticator(
  auth:
    ReconstructedLogresQuestAuthenticator,
): ReconstructedLogresQuestAuthenticator {
  return {
    actorRef:
      requireNonEmptyLocalKey(
        auth.actorRef,
      ),
    sessionToken:
      requireNonEmptyLocalKey(
        auth.sessionToken,
      ),
  }
}

function assertAuthenticatedQuestMutation(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  auth:
    ReconstructedLogresQuestAuthenticator,
): void {
  const normalizedAuth =
    requireAuthenticator(
      auth,
    )

  if (
    normalizedAuth.actorRef !==
      state.authenticatedActorRef ||
    normalizedAuth.sessionToken !==
      state.authenticatedSessionToken
  ) {
    throw new Error(
      'Quest flow mutation rejected for unauthenticated actor/session pair',
    )
  }
}

function validateQuestFlowState(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
): void {
  if (
    state.provenance !==
    LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE
  ) {
    throw new Error(
      'Quest flow state provenance must be RECONSTRUCTED',
    )
  }

  if (
    !Number.isSafeInteger(
      state.revision,
    ) ||
    state.revision < 0
  ) {
    throw new Error(
      'Quest flow revision must be a non-negative safe integer',
    )
  }
}

function nextQuestFlowState(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  patch: {
    phase?:
      ReconstructedLogresQuestFlowPhase
    progressKeys?:
      readonly string[]
    appliedProgressRequestIds?:
      readonly string[]
    acceptRequestId?:
      | string
      | null
    completionRequestId?:
      | string
      | null
    rewardGrantKey?:
      | string
      | null
    originalCompletionRef?:
      | string
      | null
    originalRewardRef?:
      | string
      | null
  },
): Readonly<ReconstructedLogresQuestFlowState> {
  if (
    state.revision ===
    Number.MAX_SAFE_INTEGER
  ) {
    throw new Error(
      'Quest flow revision exceeds safe integer range',
    )
  }

  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
    revision:
      state.revision +
      1,
    instance:
      state.instance,
    phase:
      patch.phase ??
      state.phase,
    authenticatedActorRef:
      state.authenticatedActorRef,
    authenticatedSessionToken:
      state.authenticatedSessionToken,
    originalQuestUid:
      state.originalQuestUid,
    progressKeys:
      Object.freeze([
        ...(
          patch.progressKeys ??
          state.progressKeys
        ),
      ]),
    appliedProgressRequestIds:
      Object.freeze([
        ...(
          patch.appliedProgressRequestIds ??
          state.appliedProgressRequestIds
        ),
      ]),
    acceptRequestId:
      patch.acceptRequestId ??
      state.acceptRequestId,
    completionRequestId:
      patch.completionRequestId ??
      state.completionRequestId,
    rewardGrantKey:
      patch.rewardGrantKey ??
      state.rewardGrantKey,
    originalCompletionRef:
      patch.originalCompletionRef ??
      state.originalCompletionRef,
    originalRewardRef:
      patch.originalRewardRef ??
      state.originalRewardRef,
  })
}

/**
 * Creates a reconstruction-local quest flow state that remains explicitly
 * server-authoritative and authenticated.
 *
 * RECONSTRUCTED contract:
 * - accept/progress/completion/reward transitions are applied by the authority
 *   state only
 * - unknown historical identifiers remain nullable
 * - actor/session ownership is explicit for persistence and replay safety
 */
export function createReconstructedLogresQuestFlowState(
  input: {
    instance:
      Readonly<ReconstructedLogresQuestInstance>
    authenticator:
      ReconstructedLogresQuestAuthenticator
    originalQuestUid:
      | string
      | null
  },
): Readonly<ReconstructedLogresQuestFlowState> {
  const authenticator =
    requireAuthenticator(
      input.authenticator,
    )

  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
    revision:
      0,
    instance:
      input.instance,
    phase:
      'issued',
    authenticatedActorRef:
      authenticator.actorRef,
    authenticatedSessionToken:
      authenticator.sessionToken,
    originalQuestUid:
      requireOptionalString(
        input.originalQuestUid,
        'Quest originalQuestUid',
      ),
    progressKeys:
      Object.freeze(
        [],
      ),
    appliedProgressRequestIds:
      Object.freeze(
        [],
      ),
    acceptRequestId:
      null,
    completionRequestId:
      null,
    rewardGrantKey:
      null,
    originalCompletionRef:
      null,
    originalRewardRef:
      null,
  })
}

export function applyReconstructedLogresQuestAccept(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  input: {
    requestId: string
    authenticator:
      ReconstructedLogresQuestAuthenticator
  },
): ReconstructedLogresQuestFlowApplyResult {
  validateQuestFlowState(
    state,
  )
  assertAuthenticatedQuestMutation(
    state,
    input.authenticator,
  )

  const requestId =
    requireNonEmptyLocalKey(
      input.requestId,
    )

  if (
    state.acceptRequestId ===
    requestId
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  if (
    state.acceptRequestId !==
    null
  ) {
    throw new Error(
      'Quest flow already accepted by a different request id',
    )
  }

  if (
    state.phase !==
    'issued'
  ) {
    throw new Error(
      'Quest accept requires issued phase',
    )
  }

  return {
    applied:
      true,
    state:
      nextQuestFlowState(
        state,
        {
          phase:
            'accepted',
          acceptRequestId:
            requestId,
        },
      ),
  }
}

export function applyReconstructedLogresQuestProgress(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  input: {
    requestId: string
    progressKey: string
    authenticator:
      ReconstructedLogresQuestAuthenticator
  },
): ReconstructedLogresQuestFlowApplyResult {
  validateQuestFlowState(
    state,
  )
  assertAuthenticatedQuestMutation(
    state,
    input.authenticator,
  )

  const requestId =
    requireNonEmptyLocalKey(
      input.requestId,
    )

  if (
    state
      .appliedProgressRequestIds
      .includes(
        requestId,
      )
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  if (
    state.phase ===
    'issued'
  ) {
    throw new Error(
      'Quest progress requires accepted phase',
    )
  }

  if (
    state.phase ===
      'completed' ||
    state.phase ===
      'reward-granted'
  ) {
    throw new Error(
      'Quest progress cannot advance after completion',
    )
  }

  const progressKey =
    requireNonEmptyLocalKey(
      input.progressKey,
    )

  if (
    state.progressKeys.includes(
      progressKey,
    )
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  return {
    applied:
      true,
    state:
      nextQuestFlowState(
        state,
        {
          phase:
            'in-progress',
          progressKeys: [
            ...state.progressKeys,
            progressKey,
          ],
          appliedProgressRequestIds:
            [
              ...state.appliedProgressRequestIds,
              requestId,
            ],
        },
      ),
  }
}

export function applyReconstructedLogresQuestCompletion(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  input: {
    requestId: string
    authenticator:
      ReconstructedLogresQuestAuthenticator
    originalCompletionRef:
      | string
      | null
  },
): ReconstructedLogresQuestFlowApplyResult {
  validateQuestFlowState(
    state,
  )
  assertAuthenticatedQuestMutation(
    state,
    input.authenticator,
  )

  const requestId =
    requireNonEmptyLocalKey(
      input.requestId,
    )

  if (
    state.completionRequestId ===
    requestId
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  if (
    state.completionRequestId !==
    null
  ) {
    throw new Error(
      'Quest completion already recorded by a different request id',
    )
  }

  if (
    state.phase ===
    'issued'
  ) {
    throw new Error(
      'Quest completion requires accepted or in-progress phase',
    )
  }

  if (
    state.phase ===
    'reward-granted'
  ) {
    throw new Error(
      'Quest completion cannot be changed after reward grant',
    )
  }

  return {
    applied:
      true,
    state:
      nextQuestFlowState(
        state,
        {
          phase:
            'completed',
          completionRequestId:
            requestId,
          originalCompletionRef:
            requireOptionalString(
              input.originalCompletionRef,
              'Quest originalCompletionRef',
            ),
        },
      ),
  }
}

export function applyReconstructedLogresQuestRewardGrant(
  state:
    Readonly<ReconstructedLogresQuestFlowState>,
  input: {
    grantKey: string
    authenticator:
      ReconstructedLogresQuestAuthenticator
    originalRewardRef:
      | string
      | null
  },
): ReconstructedLogresQuestFlowApplyResult {
  validateQuestFlowState(
    state,
  )
  assertAuthenticatedQuestMutation(
    state,
    input.authenticator,
  )

  const grantKey =
    requireNonEmptyLocalKey(
      input.grantKey,
    )

  if (
    state.rewardGrantKey ===
    grantKey
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  if (
    state.rewardGrantKey !==
    null
  ) {
    throw new Error(
      'Quest reward already granted by a different grant key',
    )
  }

  if (
    state.phase !==
      'completed' &&
    state.phase !==
      'reward-granted'
  ) {
    throw new Error(
      'Quest reward grant requires completed phase',
    )
  }

  return {
    applied:
      true,
    state:
      nextQuestFlowState(
        state,
        {
          phase:
            'reward-granted',
          rewardGrantKey:
            grantKey,
          originalRewardRef:
            requireOptionalString(
              input.originalRewardRef,
              'Quest originalRewardRef',
            ),
        },
      ),
  }
}
