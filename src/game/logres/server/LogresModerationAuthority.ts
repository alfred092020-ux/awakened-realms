/*
 * Server-owned moderation and RBAC authority.
 *
 * All role assignment, sanctioning, and audit recording happens
 * server-side. Clients may submit reports and appeals, but the server is
 * the sole authority on roles, sanctions, and the append-only audit log.
 * This module fails closed: unknown actors, insufficient roles, malformed
 * sanctions, and any audit tampering throw.
 */

export const LOGRES_MODERATION_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Role-Based Access Control roles.
 *
 * Ordering reflects increasing privilege: player < moderator < admin.
 */
export type LogresModerationRole =
  | 'player'
  | 'moderator'
  | 'admin'

const ROLE_RANK:
  Record<
    LogresModerationRole,
    number
  > = {
  player: 0,
  moderator: 1,
  admin: 2,
}

/**
 * Sanction kinds the server may apply to a subject.
 */
export type LogresSanctionKind =
  | 'mute'
  | 'ban'

export interface LogresSanction {
  sanctionKey: string
  subjectUid: string
  kind: LogresSanctionKind
  reason: string
  issuedByUid: string
  issuedAtSeconds: number
  /**
   * Expiry in seconds; null means the sanction does not expire.
   */
  expiresAtSeconds:
    | number
    | null
  active: boolean
}

/**
 * Append-only audit event. `sequence` is assigned by the server and is
 * monotonically increasing; events are never edited or removed.
 */
export interface LogresAuditEvent {
  sequence: number
  actorUid: string
  actorRole: LogresModerationRole
  action: string
  targetUid: string | null
  detail: string
  atSeconds: number
}

export interface LogresModerationState {
  provenance:
    typeof LOGRES_MODERATION_PROVENANCE
  revision: number
  rolesByUid:
    Readonly<
      Record<
        string,
        LogresModerationRole
      >
    >
  sanctions:
    readonly Readonly<LogresSanction>[]
  auditLog:
    readonly Readonly<LogresAuditEvent>[]
  nextAuditSequence: number
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

function requireRole(
  value: unknown,
): LogresModerationRole {
  if (
    value !== 'player' &&
    value !== 'moderator' &&
    value !== 'admin'
  ) {
    throw new Error(
      'Role must be player, moderator, or admin',
    )
  }

  return value
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

function roleRank(
  role: LogresModerationRole,
): number {
  return ROLE_RANK[role]
}

function getRole(
  state: LogresModerationState,
  uid: string,
): LogresModerationRole {
  return (
    state.rolesByUid[uid] ??
    'player'
  )
}

function requireActorRoleAtLeast(
  state: LogresModerationState,
  actorUid: string,
  minimum: LogresModerationRole,
): LogresModerationRole {
  const role =
    getRole(
      state,
      actorUid,
    )

  if (
    roleRank(role) <
    roleRank(minimum)
  ) {
    throw new Error(
      `Actor role ${role} is below required ${minimum}`,
    )
  }

  return role
}

function appendAudit(
  state: LogresModerationState,
  actorUid: string,
  actorRole: LogresModerationRole,
  action: string,
  targetUid: string | null,
  detail: string,
  atSeconds: number,
): readonly Readonly<LogresAuditEvent>[] {
  const event:
    LogresAuditEvent = {
    sequence:
      state.nextAuditSequence,
    actorUid,
    actorRole,
    action,
    targetUid,
    detail,
    atSeconds,
  }

  return Object.freeze([
    ...state.auditLog,
    Object.freeze(
      event,
    ),
  ])
}

function freezeState(
  revision: number,
  rolesByUid:
    Record<
      string,
      LogresModerationRole
    >,
  sanctions:
    readonly LogresSanction[],
  auditLog:
    readonly Readonly<LogresAuditEvent>[],
  nextAuditSequence: number,
): LogresModerationState {
  return Object.freeze({
    provenance:
      LOGRES_MODERATION_PROVENANCE,
    revision,
    rolesByUid:
      Object.freeze({
        ...rolesByUid,
      }),
    sanctions:
      Object.freeze(
        sanctions.map(
          (s) =>
            Object.freeze({
              ...s,
            }),
        ),
      ),
    auditLog,
    nextAuditSequence,
  })
}

export function createLogresModerationState(
  adminUids:
    readonly string[],
): LogresModerationState {
  const roles:
    Record<
      string,
      LogresModerationRole
    > = {}

  for (const uid of adminUids) {
    const normalized =
      requireNonEmpty(
        uid,
        'Admin uid',
      )
    roles[normalized] =
      'admin'
  }

  return freezeState(
    0,
    roles,
    [],
    Object.freeze([]),
    1,
  )
}

/**
 * Assigns a role to a subject. Only admins may grant roles, and an admin
 * cannot grant a role higher than their own.
 */
export function assignLogresRole(
  state: LogresModerationState,
  actorUid: string,
  subjectUid: string,
  role: LogresModerationRole,
  atSeconds: number,
): LogresModerationState {
  if (
    state.provenance !==
    LOGRES_MODERATION_PROVENANCE
  ) {
    throw new Error(
      'Moderation provenance must be RECONSTRUCTED',
    )
  }

  const actor =
    requireNonEmpty(
      actorUid,
      'Actor uid',
    )
  const subject =
    requireNonEmpty(
      subjectUid,
      'Subject uid',
    )
  const targetRole =
    requireRole(role)
  const at =
    requireSafeInteger(
      atSeconds,
      'Assignment atSeconds',
    )

  const actorRole =
    requireActorRoleAtLeast(
      state,
      actor,
      'admin',
    )

  if (
    roleRank(targetRole) >
    roleRank(actorRole)
  ) {
    throw new Error(
      'Actor cannot grant a role above their own',
    )
  }

  const rolesByUid = {
    ...state.rolesByUid,
    [subject]:
      targetRole,
  }

  const auditLog =
    appendAudit(
      state,
      actor,
      actorRole,
      'assign-role',
      subject,
      `role=${targetRole}`,
      at,
    )

  return freezeState(
    state.revision + 1,
    rolesByUid,
    state.sanctions,
    auditLog,
    state.nextAuditSequence +
      1,
  )
}

/**
 * Issues a mute or ban. Moderators and admins may sanction players; an
 * actor cannot sanction a subject whose role rank is >= their own.
 */
export function issueLogresSanction(
  state: LogresModerationState,
  actorUid: string,
  sanction:
    Omit<
      LogresSanction,
      | 'issuedByUid'
      | 'issuedAtSeconds'
      | 'active'
    >,
  atSeconds: number,
): LogresModerationState {
  if (
    state.provenance !==
    LOGRES_MODERATION_PROVENANCE
  ) {
    throw new Error(
      'Moderation provenance must be RECONSTRUCTED',
    )
  }

  const actor =
    requireNonEmpty(
      actorUid,
      'Actor uid',
    )

  const actorRole =
    requireActorRoleAtLeast(
      state,
      actor,
      'moderator',
    )

  const subject =
    requireNonEmpty(
      sanction.subjectUid,
      'Sanction subjectUid',
    )

  const subjectRole =
    getRole(
      state,
      subject,
    )

  if (
    roleRank(subjectRole) >=
    roleRank(actorRole)
  ) {
    throw new Error(
      'Cannot sanction a subject with equal or higher role',
    )
  }

  const kind = sanction.kind
  if (
    kind !== 'mute' &&
    kind !== 'ban'
  ) {
    throw new Error(
      'Sanction kind must be mute or ban',
    )
  }

  const sanctionKey =
    requireNonEmpty(
      sanction.sanctionKey,
      'Sanction sanctionKey',
    )

  if (
    state.sanctions.some(
      (s) =>
        s.sanctionKey ===
        sanctionKey,
    )
  ) {
    throw new Error(
      'Sanction sanctionKey must be unique',
    )
  }

  const at =
    requireSafeInteger(
      atSeconds,
      'Sanction atSeconds',
    )

  const expires =
    sanction.expiresAtSeconds ===
    null
      ? null
      : requireSafeInteger(
          sanction.expiresAtSeconds,
          'Sanction expiresAtSeconds',
        )

  if (
    expires !== null &&
    expires <= at
  ) {
    throw new Error(
      'Sanction expiresAtSeconds must be after issuance',
    )
  }

  const issued:
    LogresSanction = {
    sanctionKey,
    subjectUid: subject,
    kind,
    reason:
      requireNonEmpty(
        sanction.reason,
        'Sanction reason',
      ),
    issuedByUid: actor,
    issuedAtSeconds: at,
    expiresAtSeconds:
      expires,
    active: true,
  }

  const auditLog =
    appendAudit(
      state,
      actor,
      actorRole,
      `issue-${kind}`,
      subject,
      `sanctionKey=${sanctionKey}`,
      at,
    )

  return freezeState(
    state.revision + 1,
    state.rolesByUid,
    [
      ...state.sanctions,
      issued,
    ],
    auditLog,
    state.nextAuditSequence +
      1,
  )
}

/**
 * Returns the currently-active sanction of a kind for a subject, or null.
 */
export function getActiveLogresSanction(
  state: LogresModerationState,
  subjectUid: string,
  kind: LogresSanctionKind,
  atSeconds: number,
): Readonly<LogresSanction> | null {
  if (
    state.provenance !==
    LOGRES_MODERATION_PROVENANCE
  ) {
    throw new Error(
      'Moderation provenance must be RECONSTRUCTED',
    )
  }

  const at =
    requireSafeInteger(
      atSeconds,
      'Sanction atSeconds',
    )

  const found =
    state.sanctions.find(
      (s) =>
        s.subjectUid ===
          subjectUid &&
        s.kind === kind &&
        s.active &&
        (
          s.expiresAtSeconds ===
            null ||
          s.expiresAtSeconds >
            at
        ),
    )

  return found ?? null
}

/**
 * Reads the audit log. The log is append-only; callers receive a frozen
 * snapshot and cannot mutate history.
 */
export function readLogresAuditLog(
  state: LogresModerationState,
): readonly Readonly<LogresAuditEvent>[] {
  if (
    state.provenance !==
    LOGRES_MODERATION_PROVENANCE
  ) {
    throw new Error(
      'Moderation provenance must be RECONSTRUCTED',
    )
  }

  return state.auditLog
}
