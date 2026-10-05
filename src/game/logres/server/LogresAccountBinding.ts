/*
 * Server-side account binding contract.
 *
 * A guest account is created when a player signs in with Firebase anonymous
 * auth and the server verifies the resulting token as provider `guest`. All
 * guest progression lives under a server-owned account id — never a
 * client-asserted uid — so it survives a later binding.
 *
 * Binding a guest account to a permanent identity (Google or email/password
 * subject) is:
 *   - explicit: only `bindLogresGuestAccount` performs it
 *   - atomic at the contract level: the binding record, subject index, and
 *     account principal update commit together or not at all
 *   - idempotent: replaying the same verified binding returns the existing
 *     record without re-mutating state
 *
 * Hard rejections:
 *   - binding to a credential subject already owned by a different account
 *   - rebinding an already-bound account to a different subject
 *   - binding a non-guest account or an already-bound guest as `guest`
 *   - any client-asserted uid: the only trusted identities are the
 *     server-verified session identity and the server-verified target
 *     subject
 */

import type {
  LogresAuthProvider,
  LogresServerAuthSession,
  LogresSessionClock,
  LogresTokenVerifier,
  LogresVerifiedIdentity,
} from './LogresAuthSession'

import {
  requireActiveLogresServerAuthSession,
} from './LogresAuthSession'

export const LOGRES_ACCOUNT_BINDING_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Permanent providers a guest account can bind to. `guest` is excluded: a
 * guest cannot be "bound" to another anonymous identity.
 */
export type LogresBindableProvider =
  Exclude<
    LogresAuthProvider,
    'guest'
  >

/**
 * A permanent identity subject, server-verified during binding.
 *
 * `subjectUid` is the verified Firebase uid of the Google or password
 * credential the guest account is being bound to.
 */
export interface LogresBoundSubject {
  provider: LogresBindableProvider
  subjectUid: string
  email: string | null
}

/**
 * A server-owned account record. `accountId` is assigned by the server and
 * is the durable identity that progression, persistence, and binding are
 * keyed on; Firebase uids and session keys never replace it.
 */
export interface LogresAccountRecord {
  accountId: string
  createdAtSeconds: number
  guest: boolean
  guestUid: string
  /**
   * Null while the account is guest-only; populated exactly once by a
   * successful binding.
   */
  boundSubject:
    Readonly<LogresBoundSubject> | null
}

/**
 * The applied binding event, recorded for audit and idempotent replay.
 */
export interface LogresAccountBindingEvent {
  accountId: string
  guestUid: string
  subject: Readonly<LogresBoundSubject>
  boundAtSeconds: number
  /**
   * Server-scoped idempotency key: `${accountId}:${subjectKey}`.
   */
  bindingKey: string
}

export interface LogresAccountBindingState {
  provenance:
    typeof LOGRES_ACCOUNT_BINDING_PROVENANCE
  accounts:
    Readonly<Record<string, Readonly<LogresAccountRecord>>>
  /**
   * Verified permanent subject key (`${provider}:${subjectUid}`) to owning
   * accountId. Enforces the one-account-per-subject invariant.
   */
  subjectOwners:
    Readonly<Record<string, string>>
  bindings:
    readonly Readonly<LogresAccountBindingEvent>[]
}

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

function requireBindableProvider(
  value: unknown,
): LogresBindableProvider {
  if (
    value !== 'google' &&
    value !== 'password'
  ) {
    throw new Error(
      'Bind target provider must be "google" or "password"',
    )
  }

  return value
}

function subjectKeyOf(
  provider: LogresBindableProvider,
  subjectUid: string,
): string {
  return `${provider}:${subjectUid}`
}

function freezeAccount(
  account: LogresAccountRecord,
): Readonly<LogresAccountRecord> {
  return Object.freeze({
    accountId:
      account.accountId,
    createdAtSeconds:
      account.createdAtSeconds,
    guest:
      account.guest,
    guestUid:
      account.guestUid,
    boundSubject:
      account.boundSubject
        ? Object.freeze({
            provider:
              account
                .boundSubject
                .provider,
            subjectUid:
              account
                .boundSubject
                .subjectUid,
            email:
              account
                .boundSubject
                .email,
          })
        : null,
  })
}

function freezeState(
  accounts: Record<string, Readonly<LogresAccountRecord>>,
  subjectOwners: Record<string, string>,
  bindings: readonly Readonly<LogresAccountBindingEvent>[],
): LogresAccountBindingState {
  return {
    provenance:
      LOGRES_ACCOUNT_BINDING_PROVENANCE,
    accounts:
      Object.freeze(
        accounts,
      ),
    subjectOwners:
      Object.freeze(
        subjectOwners,
      ),
    bindings:
      Object.freeze(
        bindings.slice(),
      ),
  }
}

/**
 * Creates the empty server-owned binding registry.
 */
export function createLogresAccountBindingState(): LogresAccountBindingState {
  return freezeState(
    {},
    {},
    [],
  )
}

/**
 * Registers a new guest account from a server-verified guest session.
 *
 * The `accountId` must be server-generated; the verified session uid is
 * recorded only as `guestUid` provenance. Replay-safe: registering the same
 * guest uid under the same accountId returns the existing account.
 */
export function registerLogresGuestAccount(
  state: LogresAccountBindingState,
  session: LogresServerAuthSession,
  clock: LogresSessionClock,
  accountId: string,
): LogresAccountBindingState {
  if (
    state.provenance !==
    LOGRES_ACCOUNT_BINDING_PROVENANCE
  ) {
    throw new Error(
      'Account binding state provenance must be RECONSTRUCTED',
    )
  }

  const active =
    requireActiveLogresServerAuthSession(
      session,
      clock,
    )

  if (
    active.identity.provider !==
    'guest'
  ) {
    throw new Error(
      'Guest account registration requires a guest session',
    )
  }

  const normalizedAccountId =
    requireNonEmpty(
      accountId,
      'Account id',
    )

  const now =
    requireSafeInteger(
      clock.nowSeconds(),
      'Account clock nowSeconds',
    )

  const existing =
    state.accounts[
      normalizedAccountId
    ]

  if (existing) {
    // Idempotent replay of the same registration is a no-op; a collision
    // under a different guest identity is a server-side integrity fault.
    if (
      existing.guestUid !==
      active.identity.uid ||
      !existing.guest
    ) {
      throw new Error(
        'Account id is already registered to a different guest identity',
      )
    }

    return state
  }

  const next =
    freezeAccount({
      accountId:
        normalizedAccountId,
      createdAtSeconds:
        now,
      guest: true,
      guestUid:
        active.identity.uid,
      boundSubject:
        null,
    })

  return freezeState(
    {
      ...state.accounts,
      [normalizedAccountId]:
        next,
    },
    {
      ...state.subjectOwners,
    },
    state.bindings,
  )
}

/**
 * Result of a binding attempt. `applied` is false only for an idempotent
 * replay of an already-recorded binding; contract violations throw.
 */
export interface LogresAccountBindingResult {
  account: Readonly<LogresAccountRecord>
  binding:
    Readonly<LogresAccountBindingEvent>
  state: LogresAccountBindingState
  /**
   * True when this call committed a new binding; false when it replayed an
   * existing identical binding.
   */
  applied: boolean
}

/**
 * Binds a guest account to a verified permanent identity subject.
 *
 * `presentedBinding` carries the untrusted client credential for the new
 * permanent sign-in (Google or email/password). The injected verifier must
 * independently verify it; the verified uid — never a client-supplied one —
 * becomes the bound subject.
 */
export function bindLogresGuestAccount(
  state: LogresAccountBindingState,
  session: LogresServerAuthSession,
  clock: LogresSessionClock,
  verifier: LogresTokenVerifier,
  presentedBinding: {
    provider: LogresBindableProvider
    idToken: string
  },
): LogresAccountBindingResult {
  if (
    state.provenance !==
    LOGRES_ACCOUNT_BINDING_PROVENANCE
  ) {
    throw new Error(
      'Account binding state provenance must be RECONSTRUCTED',
    )
  }

  const active =
    requireActiveLogresServerAuthSession(
      session,
      clock,
    )

  if (
    active.identity.provider !==
    'guest'
  ) {
    throw new Error(
      'Only a guest session can initiate account binding',
    )
  }

  const targetProvider =
    requireBindableProvider(
      presentedBinding.provider,
    )

  const idToken =
    requireNonEmpty(
      presentedBinding.idToken,
      'Binding idToken',
    )

  const now =
    requireSafeInteger(
      clock.nowSeconds(),
      'Account clock nowSeconds',
    )

  // Locate the guest account by its verified guest uid; the client cannot
  // pick which account to bind.
  const accountEntry =
    Object
      .values(
        state.accounts,
      )
      .find(
        (account) =>
          account.guest &&
          account.guestUid ===
            active.identity.uid,
      )

  if (!accountEntry) {
    throw new Error(
      'No guest account exists for the verified guest identity',
    )
  }

  const verified =
    verifier.verifyToken(
      Object.freeze({
        provider:
          targetProvider,
        idToken,
      }),
    )

  if (
    typeof verified !== 'object' ||
    verified === null
  ) {
    throw new Error(
      'Verifier must return a verified identity object',
    )
  }

  if (
    verified.provider !==
    targetProvider
  ) {
    throw new Error(
      'Verified binding provider does not match presented provider',
    )
  }

  const subjectUid =
    requireNonEmpty(
      verified.uid,
      'Verified binding subject uid',
    )

  const email =
    verified.email ===
      null ||
    typeof verified.email ===
      'string'
      ? verified.email
      : null

  const subject:
    Readonly<LogresBoundSubject> =
      Object.freeze({
        provider:
          targetProvider,
        subjectUid,
        email,
      })

  const subjectKey =
    subjectKeyOf(
      targetProvider,
      subjectUid,
    )

  const bindingKey =
    `${accountEntry.accountId}:${subjectKey}`

  // Idempotent replay: same account, same subject, already recorded.
  const existingBinding =
    state.bindings.find(
      (binding) =>
        binding.bindingKey ===
        bindingKey,
    )

  if (
    existingBinding &&
    accountEntry.boundSubject &&
    accountEntry.boundSubject
      .provider ===
      targetProvider &&
    accountEntry.boundSubject
      .subjectUid ===
      subjectUid
  ) {
    return {
      account:
        accountEntry,
      binding:
        existingBinding,
      state,
      applied: false,
    }
  }

  // Reject rebinding an already-bound account to a different subject.
  if (
    accountEntry.boundSubject &&
    (
      accountEntry.boundSubject
        .provider !==
        targetProvider ||
      accountEntry.boundSubject
        .subjectUid !==
        subjectUid
    )
  ) {
    throw new Error(
      'Account is already bound to a different subject',
    )
  }

  // Reject binding to a subject already owned by a different account.
  const existingOwner =
    state.subjectOwners[
      subjectKey
    ]

  if (
    existingOwner &&
    existingOwner !==
      accountEntry.accountId
  ) {
    throw new Error(
      'Credential subject is already bound to a different account',
    )
  }

  const updatedAccount =
    freezeAccount({
      accountId:
        accountEntry.accountId,
      createdAtSeconds:
        accountEntry.createdAtSeconds,
      guest: true,
      guestUid:
        accountEntry.guestUid,
      boundSubject:
        subject,
    })

  const event:
    Readonly<LogresAccountBindingEvent> =
      Object.freeze({
        accountId:
          accountEntry.accountId,
        guestUid:
          accountEntry.guestUid,
        subject,
        boundAtSeconds:
          now,
        bindingKey,
      })

  const nextState =
    freezeState(
      {
        ...state.accounts,
        [accountEntry.accountId]:
          updatedAccount,
      },
      {
        ...state.subjectOwners,
        [subjectKey]:
          accountEntry.accountId,
      },
      [
        ...state.bindings,
        event,
      ],
    )

  return {
    account:
      updatedAccount,
    binding:
      event,
    state:
      nextState,
    applied: true,
  }
}

/**
 * Returns the server-owned account for a verified session identity, if any.
 *
 * For a guest session this resolves via the guest uid; for a bound permanent
 * session it resolves via the subject owner index. Returns null when no
 * account exists.
 */
export function resolveLogresAccountForSession(
  state: LogresAccountBindingState,
  identity: Readonly<LogresVerifiedIdentity>,
): Readonly<LogresAccountRecord> | null {
  if (
    state.provenance !==
    LOGRES_ACCOUNT_BINDING_PROVENANCE
  ) {
    throw new Error(
      'Account binding state provenance must be RECONSTRUCTED',
    )
  }

  if (
    identity.provider ===
    'guest'
  ) {
    return (
      Object
        .values(
          state.accounts,
        )
        .find(
          (account) =>
            account.guestUid ===
              identity.uid,
        ) ?? null
    )
  }

  const owner =
    state.subjectOwners[
      subjectKeyOf(
        requireBindableProvider(
          identity.provider,
        ),
        requireNonEmpty(
          identity.uid,
          'Session identity uid',
        ),
      )
    ]

  if (!owner) {
    return null
  }

  return (
    state.accounts[
      owner
    ] ?? null
  )
}
