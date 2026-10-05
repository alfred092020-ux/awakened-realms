/*
 * Server-owned leaderboards.
 *
 * Clients never write scores. The server applies score mutations derived
 * from authoritative gameplay events, owns ordering, and issues snapshots.
 * Score writes reference a server-side provenance key (e.g. a battle
 * outcome id) for idempotency; replays of the same event are no-ops.
 *
 * This module fails closed: malformed inputs, non-finite scores, duplicate
 * provenance keys being applied twice (except as an explicit idempotent
 * replay), and direct client writes all throw.
 */

export const LOGRES_LEADERBOARD_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Known leaderboard boards. Extensible server-side; clients only read.
 */
export type LogresLeaderboardId =
  | 'season-elo'
  | 'quest-clears'
  | 'summon-points'

export interface LogresLeaderboardEntry {
  uid: string
  score: number
  /**
   * Monotonic update counter; higher wins ties. Server-assigned.
   */
  updateSequence: number
}

export interface LogresLeaderboardState {
  provenance:
    typeof LOGRES_LEADERBOARD_PROVENANCE
  boardId: LogresLeaderboardId
  entries:
    readonly Readonly<LogresLeaderboardEntry>[]
  /**
   * Server event keys already applied, for idempotent writes.
   */
  appliedEventKeys:
    readonly string[]
  nextUpdateSequence: number
}

/**
 * A server-side score mutation derived from an authoritative game event.
 *
 * `eventKey` is the idempotency key: a replayed event must not double-count.
 */
export interface LogresLeaderboardWriteInput {
  eventKey: string
  uid: string
  /**
   * Signed score delta applied by the server. May be negative (e.g. loss).
   */
  delta: number
}

export interface LogresLeaderboardWriteResult {
  applied: boolean
  state: LogresLeaderboardState
}

const BOARD_IDS:
  readonly LogresLeaderboardId[] =
  [
    'season-elo',
    'quest-clears',
    'summon-points',
  ]

function requireBoardId(
  value: unknown,
): LogresLeaderboardId {
  if (
    typeof value !== 'string' ||
    !BOARD_IDS.includes(
      value as LogresLeaderboardId,
    )
  ) {
    throw new Error(
      'Leaderboard boardId is not a known board',
    )
  }

  return value as LogresLeaderboardId
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

function requireFiniteScore(
  value: unknown,
  label: string,
): number {
  if (
    typeof value !== 'number' ||
    !Number.isFinite(value)
  ) {
    throw new Error(
      `${label} must be a finite number`,
    )
  }

  return value
}

function sortEntries(
  entries:
    readonly LogresLeaderboardEntry[],
): readonly LogresLeaderboardEntry[] {
  return Object.freeze(
    [...entries].sort(
      (a, b) =>
        b.score - a.score ||
        b.updateSequence -
          a.updateSequence ||
        a.uid.localeCompare(
          b.uid,
        ),
    ),
  )
}

function freezeState(
  boardId: LogresLeaderboardId,
  entries:
    readonly LogresLeaderboardEntry[],
  appliedEventKeys:
    readonly string[],
  nextUpdateSequence: number,
): LogresLeaderboardState {
  return Object.freeze({
    provenance:
      LOGRES_LEADERBOARD_PROVENANCE,
    boardId,
    entries:
      sortEntries(
        entries,
      ),
    appliedEventKeys:
      Object.freeze([
        ...appliedEventKeys,
      ]),
    nextUpdateSequence,
  })
}

export function createLogresLeaderboard(
  boardId: LogresLeaderboardId,
): LogresLeaderboardState {
  return freezeState(
    requireBoardId(
      boardId,
    ),
    [],
    [],
    1,
  )
}

/**
 * Applies one server-owned score write.
 *
 * This is the ONLY way scores change. A replayed `eventKey` is a no-op so
 * retried game events never double-count. There is no client-facing write
 * path; the input is a server-internal event projection.
 */
export function applyLogresLeaderboardWrite(
  state: LogresLeaderboardState,
  input: LogresLeaderboardWriteInput,
): LogresLeaderboardWriteResult {
  if (
    state.provenance !==
    LOGRES_LEADERBOARD_PROVENANCE
  ) {
    throw new Error(
      'Leaderboard provenance must be RECONSTRUCTED',
    )
  }

  const eventKey =
    requireNonEmpty(
      input.eventKey,
      'Leaderboard eventKey',
    )

  if (
    state.appliedEventKeys.includes(
      eventKey,
    )
  ) {
    return {
      applied: false,
      state,
    }
  }

  const uid =
    requireNonEmpty(
      input.uid,
      'Leaderboard uid',
    )

  const delta =
    requireFiniteScore(
      input.delta,
      'Leaderboard delta',
    )

  const existing =
    state.entries.find(
      (e) =>
        e.uid === uid,
    )

  const nextSequence =
    state.nextUpdateSequence

  const score =
    requireFiniteScore(
      (existing?.score ?? 0) +
        delta,
      'Leaderboard resulting score',
    )

  const updated:
    LogresLeaderboardEntry = {
    uid,
    score,
    updateSequence:
      nextSequence,
  }

  const entries =
    existing
      ? state.entries.map(
          (e) =>
            e.uid === uid
              ? updated
              : e,
        )
      : [
          ...state.entries,
          updated,
        ]

  return {
    applied: true,
    state:
      freezeState(
        state.boardId,
        entries,
        [
          ...state.appliedEventKeys,
          eventKey,
        ],
        nextSequence + 1,
      ),
  }
}

/**
 * Returns a ranked read snapshot. Ties break toward the most-recently
 * updated entry, then uid for determinism.
 */
export function readLogresLeaderboard(
  state: LogresLeaderboardState,
): readonly Readonly<LogresLeaderboardEntry>[] {
  if (
    state.provenance !==
    LOGRES_LEADERBOARD_PROVENANCE
  ) {
    throw new Error(
      'Leaderboard provenance must be RECONSTRUCTED',
    )
  }

  return state.entries
}
