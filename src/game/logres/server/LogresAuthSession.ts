/*
 * Authenticated server-session boundary.
 *
 * Firebase client sign-in (Google, email/password, or anonymous guest) only
 * produces an untrusted client credential. The production server must verify
 * the presented token server-side, derive the session identity, and only then
 * accept client intents. Client-side Firebase auth state is NEVER game
 * authority.
 *
 * Anonymous guest sessions are first-class server sessions keyed by the
 * verified anonymous uid. A guest account can later be bound to a permanent
 * identity (Google or email/password) via the account-binding contract; the
 * binding is atomic, idempotent, and preserves the guest's server-owned
 * progression.
 *
 * This module fails closed: any malformed input, expired token, disabled
 * account, or mismatched identity rejects the session.
 */

export const LOGRES_SERVER_AUTH_SESSION_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Signed-in provider channel, as verified by the server.
 *
 * `guest` denotes a Firebase anonymous-auth session; `google` and
 * `password` denote permanently-credentialed accounts.
 */
export type LogresAuthProvider =
  | 'guest'
  | 'google'
  | 'password'

/**
 * Verified identity claims extracted from a server-verified token.
 *
 * `uid` is the server-trusted stable subject. All mutable profile fields are
 * advisory display data only.
 */
export interface LogresVerifiedIdentity {
  uid: string
  provider: LogresAuthProvider
  email: string | null
  displayName: string | null
  disabled: boolean
  tokenIssuedAtSeconds: number
  tokenExpiresAtSeconds: number
}

/**
 * Untrusted credential material presented by the client.
 *
 * The server never treats this as already-authenticated; `verifyToken` must
 * validate it before a session is opened.
 */
export interface LogresPresentedCredential {
  provider: LogresAuthProvider
  idToken: string
}

/**
 * Server-side token verifier seam.
 *
 * In production this is backed by Firebase Admin `verifyIdToken`; for the
 * contract layer it is an injected pure function.
 */
export interface LogresTokenVerifier {
  verifyToken(
    credential: LogresPresentedCredential,
  ): LogresVerifiedIdentity
}

/**
 * Server-authenticated session record.
 *
 * `sessionKey` is a server-issued local identity; it is not the Firebase uid
 * and is never derived from untrusted client data.
 */
export interface LogresServerAuthSession {
  provenance:
    typeof LOGRES_SERVER_AUTH_SESSION_PROVENANCE
  sessionKey: string
  identity: Readonly<LogresVerifiedIdentity>
  issuedAtSeconds: number
  expiresAtSeconds: number
  revoked: boolean
}

/**
 * Minimal clock seam so expiry is deterministic and testable.
 */
export interface LogresSessionClock {
  nowSeconds(): number
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

function requireOptionalString(
  value: unknown,
  label: string,
): string | null {
  if (value === null) {
    return null
  }

  return requireNonEmpty(
    value,
    label,
  )
}

function requireProvider(
  value: unknown,
): LogresAuthProvider {
  if (
    value !== 'guest' &&
    value !== 'google' &&
    value !== 'password'
  ) {
    throw new Error(
      'Auth provider must be "guest", "google" or "password"',
    )
  }

  return value
}

function validateIdentity(
  identity: LogresVerifiedIdentity,
  nowSeconds: number,
): Readonly<LogresVerifiedIdentity> {
  const uid =
    requireNonEmpty(
      identity.uid,
      'Verified identity uid',
    )

  const provider =
    requireProvider(
      identity.provider,
    )

  const email =
    requireOptionalString(
      identity.email,
      'Verified identity email',
    )

  const displayName =
    requireOptionalString(
      identity.displayName,
      'Verified identity displayName',
    )

  const issued =
    requireSafeInteger(
      identity.tokenIssuedAtSeconds,
      'Verified identity tokenIssuedAtSeconds',
    )

  const expires =
    requireSafeInteger(
      identity.tokenExpiresAtSeconds,
      'Verified identity tokenExpiresAtSeconds',
    )

  if (identity.disabled !== false) {
    throw new Error(
      'Verified identity account must not be disabled',
    )
  }

  if (expires <= nowSeconds) {
    throw new Error(
      'Verified identity token is expired',
    )
  }

  if (issued > nowSeconds) {
    throw new Error(
      'Verified identity token is not yet valid',
    )
  }

  if (issued > expires) {
    throw new Error(
      'Verified identity token window is inconsistent',
    )
  }

  return Object.freeze({
    uid,
    provider,
    email,
    displayName,
    disabled: false,
    tokenIssuedAtSeconds: issued,
    tokenExpiresAtSeconds: expires,
  })
}

function freezeSession(
  sessionKey: string,
  identity: Readonly<LogresVerifiedIdentity>,
  issuedAtSeconds: number,
  expiresAtSeconds: number,
  revoked: boolean,
): LogresServerAuthSession {
  return Object.freeze({
    provenance:
      LOGRES_SERVER_AUTH_SESSION_PROVENANCE,
    sessionKey,
    identity,
    issuedAtSeconds,
    expiresAtSeconds,
    revoked,
  })
}

/**
 * Opens a server-authenticated session from a presented credential.
 *
 * Fail-closed contract:
 * - the presented credential must be well-formed and provider-consistent
 * - the injected verifier must return a fully-verified identity
 * - disabled accounts and expired/not-yet-valid tokens are rejected
 * - the session expiry is the earlier of the token expiry and the requested
 *   maximum session lifetime
 */
export function openLogresServerAuthSession(
  verifier: LogresTokenVerifier,
  credential: LogresPresentedCredential,
  clock: LogresSessionClock,
  sessionKey: string,
  maxSessionLifetimeSeconds: number,
): LogresServerAuthSession {
  const normalizedKey =
    requireNonEmpty(
      sessionKey,
      'Auth sessionKey',
    )

  const lifetime =
    requireSafeInteger(
      maxSessionLifetimeSeconds,
      'Auth maxSessionLifetimeSeconds',
    )

  if (lifetime <= 0) {
    throw new Error(
      'Auth maxSessionLifetimeSeconds must be positive',
    )
  }

  if (
    typeof credential !== 'object' ||
    credential === null
  ) {
    throw new Error(
      'Presented credential must be an object',
    )
  }

  const provider =
    requireProvider(
      credential.provider,
    )

  const idToken =
    requireNonEmpty(
      credential.idToken,
      'Presented credential idToken',
    )

  const now =
    requireSafeInteger(
      clock.nowSeconds(),
      'Auth clock nowSeconds',
    )

  const verified =
    verifier.verifyToken(
      Object.freeze({
        provider,
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

  // The verifier-decoded provider must agree with the channel the client
  // claims, so a client cannot relabel a token to a different sign-in path.
  if (
    verified.provider !== provider
  ) {
    throw new Error(
      'Verified identity provider does not match presented credential',
    )
  }

  const identity =
    validateIdentity(
      verified,
      now,
    )

  const expiresAt =
    Math.min(
      identity.tokenExpiresAtSeconds,
      now + lifetime,
    )

  if (expiresAt <= now) {
    throw new Error(
      'Computed auth session expiry is not in the future',
    )
  }

  return freezeSession(
    normalizedKey,
    identity,
    now,
    expiresAt,
    false,
  )
}

/**
 * Returns the session only if it is still valid at `nowSeconds`; otherwise
 * returns a revoked snapshot. Sessions never silently extend.
 */
export function evaluateLogresServerAuthSession(
  session: LogresServerAuthSession,
  clock: LogresSessionClock,
): LogresServerAuthSession {
  if (
    session.provenance !==
    LOGRES_SERVER_AUTH_SESSION_PROVENANCE
  ) {
    throw new Error(
      'Auth session provenance must be RECONSTRUCTED',
    )
  }

  const now =
    requireSafeInteger(
      clock.nowSeconds(),
      'Auth clock nowSeconds',
    )

  if (
    session.revoked ||
    now >= session.expiresAtSeconds
  ) {
    return freezeSession(
      session.sessionKey,
      session.identity,
      session.issuedAtSeconds,
      session.expiresAtSeconds,
      true,
    )
  }

  return session
}

/**
 * Revokes a session, returning an immutable revoked snapshot.
 */
export function revokeLogresServerAuthSession(
  session: LogresServerAuthSession,
): LogresServerAuthSession {
  if (
    session.provenance !==
    LOGRES_SERVER_AUTH_SESSION_PROVENANCE
  ) {
    throw new Error(
      'Auth session provenance must be RECONSTRUCTED',
    )
  }

  return freezeSession(
    session.sessionKey,
    session.identity,
    session.issuedAtSeconds,
    session.expiresAtSeconds,
    true,
  )
}

/**
 * Asserts a session is currently valid. Throws on expired or revoked
 * sessions so callers cannot accidentally continue with stale identity.
 */
export function requireActiveLogresServerAuthSession(
  session: LogresServerAuthSession,
  clock: LogresSessionClock,
): LogresServerAuthSession {
  const evaluated =
    evaluateLogresServerAuthSession(
      session,
      clock,
    )

  if (evaluated.revoked) {
    throw new Error(
      'Auth session is expired or revoked',
    )
  }

  return evaluated
}
