/*
 * Production server-authority boundary.
 *
 * Clients send typed *intents* only. The server owns all authoritative
 * mutation: battle outcome, progression, currencies, inventory, rewards,
 * summons, purchases, and leaderboard writes. Every mutation is gated on a
 * valid, unexpired, unrevoked session derived from a server-verified
 * identity — never from client-reported Firebase auth state.
 *
 * All mutation inputs carry a server-side idempotency key so retried
 * intents cannot double-apply. Sanctioned subjects (banned) fail closed.
 * Unknown intent types and malformed payloads throw.
 */

import type {
  LogresServerAuthSession,
  LogresSessionClock,
} from './LogresAuthSession'

import {
  requireActiveLogresServerAuthSession,
} from './LogresAuthSession'

import type {
  LogresModerationState,
} from './LogresModerationAuthority'

import {
  getActiveLogresSanction,
} from './LogresModerationAuthority'

export const LOGRES_PRODUCTION_AUTHORITY_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * The exhaustive set of server-authoritative mutation kinds.
 *
 * Clients select a kind and supply an intent payload; the server computes
 * the resulting state change. There is no client-side "apply" path.
 */
export type LogresMutationKind =
  | 'battle-outcome'
  | 'progression'
  | 'currency'
  | 'inventory'
  | 'reward'
  | 'summon'
  | 'purchase'
  | 'leaderboard-write'

/**
 * Untrusted client intent. The server validates every field; the client
 * cannot set uid, timestamps, or the idempotency key used for storage.
 */
export interface LogresMutationIntent {
  /**
   * Server-assigned idempotency key scope; the client supplies a
   * client-generated nonce that the server binds to the session uid so the
   * same nonce cannot collide across players.
   */
  intentKey: string
  kind: LogresMutationKind
  /**
   * Kind-specific payload. Opaque here; validated per-kind server-side.
   */
  payload: Readonly<Record<string, unknown>>
}

/**
 * A recorded, applied mutation in the server ledger.
 */
export interface LogresAppliedMutation {
  /**
   * Server-scoped idempotency key: `${uid}:${intentKey}`.
   */
  mutationKey: string
  uid: string
  kind: LogresMutationKind
  payload: Readonly<Record<string, unknown>>
  appliedAtSeconds: number
  /**
   * Monotonic per-authority sequence.
   */
  sequence: number
}

export interface LogresMutationRejection {
  applied: false
  reason:
    | 'banned'
    | 'duplicate-intent'
    | 'invalid-intent'
    | 'unknown-kind'
}

export interface LogresMutationAccepted {
  applied: true
  mutation:
    Readonly<LogresAppliedMutation>
  state: LogresProductionAuthorityState
}

export type LogresMutationResult =
  | LogresMutationAccepted
  | LogresMutationRejection

export interface LogresProductionAuthorityState {
  provenance:
    typeof LOGRES_PRODUCTION_AUTHORITY_PROVENANCE
  appliedMutations:
    readonly Readonly<LogresAppliedMutation>[]
  appliedMutationKeys:
    readonly string[]
  nextSequence: number
}

const MUTATION_KINDS:
  readonly LogresMutationKind[] =
  [
    'battle-outcome',
    'progression',
    'currency',
    'inventory',
    'reward',
    'summon',
    'purchase',
    'leaderboard-write',
  ]

function requireNonEmpty(
  value: unknown,
  label: string,
): string {
  if (
    typeof value !== 'string' ||
    !value.trim()
  ) {
    throw new Error(
      `${label} must be a non-empty string`,
    )
  }

  return value.trim()
}

function requireSafeInteger(
  value: unknown,
  label: string,
): number {
  if (
    typeof value !== 'number' ||
    !Number.isSafeInteger(value)
  ) {
    throw new Error(
      `${label} must be a safe integer`,
    )
  }

  return value
}

function requireMutationKind(
  value: unknown,
): LogresMutationKind {
  if (
    typeof value !== 'string' ||
    !MUTATION_KINDS.includes(
      value as LogresMutationKind,
    )
  ) {
    throw new Error(
      'Mutation kind is not a known authoritative kind',
    )
  }

  return value as LogresMutationKind
}

function validatePayload(
  kind: LogresMutationKind,
  payload: Readonly<Record<string, unknown>>,
): Readonly<Record<string, unknown>> {
  if (
    typeof payload !== 'object' ||
    payload === null
  ) {
    throw new Error(
      'Mutation payload must be an object',
    )
  }

  // Per-kind minimum validation. The server enforces the fields it relies
  // on for authoritative computation; unknown extra fields are tolerated
  // but never trusted.
  switch (kind) {
    case 'battle-outcome':
      if (
        typeof payload.victory !==
        'boolean'
      ) {
        throw new Error(
          'battle-outcome requires a boolean victory',
        )
      }
      break
    case 'currency': {
      const amount =
        payload.amount
      if (
        typeof amount !== 'number' ||
        !Number.isSafeInteger(amount)
      ) {
        throw new Error(
          'currency requires a safe-integer amount',
        )
      }
      break
    }
    case 'summon':
    case 'purchase':
      if (
        typeof payload.sku !==
          'string' ||
        !payload.sku.trim()
      ) {
        throw new Error(
          `${kind} requires a non-empty sku`,
        )
      }
      break
    case 'leaderboard-write':
      // Clients may never submit leaderboard writes directly; they are
      // projected from server events. Reject a client-originated write.
      throw new Error(
        'leaderboard-write is server-internal only',
      )
    default:
      break
  }

  return Object.freeze({
    ...payload,
  })
}

function freezeState(
  appliedMutations:
    readonly LogresAppliedMutation[],
  appliedMutationKeys:
    readonly string[],
  nextSequence: number,
): LogresProductionAuthorityState {
  return Object.freeze({
    provenance:
      LOGRES_PRODUCTION_AUTHORITY_PROVENANCE,
    appliedMutations:
      Object.freeze(
        appliedMutations.map(
          (m) =>
            Object.freeze({
              ...m,
              payload:
                Object.freeze({
                  ...m.payload,
                }),
            }),
        ),
      ),
    appliedMutationKeys:
      Object.freeze([
        ...appliedMutationKeys,
      ]),
    nextSequence,
  })
}

export function createLogresProductionAuthority():
  LogresProductionAuthorityState {
  return freezeState(
    [],
    [],
    1,
  )
}

/**
 * Applies a client intent under full server authority.
 *
 * Requires an active session. The uid is taken from the verified session
 * identity — never from the intent payload. Banned sessions fail closed.
 * Replays of the same uid+intentKey are idempotent no-ops.
 */
export function applyLogresMutationIntent(
  state: LogresProductionAuthorityState,
  moderation: LogresModerationState,
  session: LogresServerAuthSession,
  clock: LogresSessionClock,
  intent: LogresMutationIntent,
): LogresMutationResult {
  if (
    state.provenance !==
    LOGRES_PRODUCTION_AUTHORITY_PROVENANCE
  ) {
    throw new Error(
      'Production authority provenance must be RECONSTRUCTED',
    )
  }

  // Session must be valid; this throws on expired/revoked.
  const active =
    requireActiveLogresServerAuthSession(
      session,
      clock,
    )

  const uid =
    active.identity.uid

  const now =
    requireSafeInteger(
      clock.nowSeconds(),
      'Authority nowSeconds',
    )

  // Banned subjects fail closed before any intent processing.
  if (
    getActiveLogresSanction(
      moderation,
      uid,
      'ban',
      now,
    ) !== null
  ) {
    return {
      applied: false,
      reason:
        'banned',
    }
  }

  if (
    typeof intent !== 'object' ||
    intent === null
  ) {
    return {
      applied: false,
      reason:
        'invalid-intent',
    }
  }

  const kind =
    requireMutationKind(
      intent.kind,
    )

  const intentKey =
    requireNonEmpty(
      intent.intentKey,
      'Mutation intentKey',
    )

  // Scope the idempotency key to the session uid so one player's nonce
  // cannot collide with another's.
  const mutationKey =
    `${uid}:${intentKey}`

  if (
    state.appliedMutationKeys.includes(
      mutationKey,
    )
  ) {
    return {
      applied: false,
      reason:
        'duplicate-intent',
    }
  }

  const payload =
    validatePayload(
      kind,
      intent.payload,
    )

  const mutation:
    LogresAppliedMutation = {
    mutationKey,
    uid,
    kind,
    payload,
    appliedAtSeconds: now,
    sequence:
      state.nextSequence,
  }

  return {
    applied: true,
    mutation:
      Object.freeze(
        mutation,
      ),
    state:
      freezeState(
        [
          ...state.appliedMutations,
          mutation,
        ],
        [
          ...state.appliedMutationKeys,
          mutationKey,
        ],
        state.nextSequence +
          1,
      ),
  }
}

/**
 * Applies a server-internal mutation that did not originate from a client
 * intent (e.g. a leaderboard write projected from a battle outcome). Uses
 * the same idempotency-ledger semantics but bypasses the client-facing
 * leaderboard-write block.
 */
export function applyLogresServerInternalMutation(
  state: LogresProductionAuthorityState,
  uid: string,
  kind: LogresMutationKind,
  mutationKeySuffix: string,
  payload: Readonly<Record<string, unknown>>,
  nowSeconds: number,
): LogresMutationResult {
  if (
    state.provenance !==
    LOGRES_PRODUCTION_AUTHORITY_PROVENANCE
  ) {
    throw new Error(
      'Production authority provenance must be RECONSTRUCTED',
    )
  }

  const subject =
    requireNonEmpty(
      uid,
      'Internal mutation uid',
    )
  const normalizedKind =
    requireMutationKind(kind)
  const suffix =
    requireNonEmpty(
      mutationKeySuffix,
      'Internal mutation key suffix',
    )
  const now =
    requireSafeInteger(
      nowSeconds,
      'Internal mutation nowSeconds',
    )

  const mutationKey =
    `${subject}:internal:${suffix}`

  if (
    state.appliedMutationKeys.includes(
      mutationKey,
    )
  ) {
    return {
      applied: false,
      reason:
        'duplicate-intent',
    }
  }

  const validated =
    Object.freeze({
      ...payload,
    })

  const mutation:
    LogresAppliedMutation = {
    mutationKey,
    uid: subject,
    kind: normalizedKind,
    payload: validated,
    appliedAtSeconds: now,
    sequence:
      state.nextSequence,
  }

  return {
    applied: true,
    mutation:
      Object.freeze(
        mutation,
      ),
    state:
      freezeState(
        [
          ...state.appliedMutations,
          mutation,
        ],
        [
          ...state.appliedMutationKeys,
          mutationKey,
        ],
        state.nextSequence +
          1,
      ),
  }
}
