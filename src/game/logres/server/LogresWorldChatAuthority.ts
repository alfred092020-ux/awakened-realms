/*
 * Server-authoritative world chat.
 *
 * Clients submit message intents only. The server validates content,
 * enforces rate limits and mutes/bans, assigns sequence numbers and
 * timestamps, and owns the canonical message log. Clients never write to
 * the log directly and cannot set their own identity or timestamps.
 *
 * This module fails closed: malformed intents, rate-limit violations,
 * sanctioned senders, invalid provenance, and message log tampering all
 * throw or are rejected.
 */

import type {
  LogresModerationState,
} from './LogresModerationAuthority'

import {
  getActiveLogresSanction,
} from './LogresModerationAuthority'

export const LOGRES_WORLD_CHAT_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Maximum accepted body length for a world-chat message.
 */
export const LOGRES_WORLD_CHAT_MAX_BODY_LENGTH =
  400

/**
 * Minimum spacing between accepted messages from one sender.
 */
export const LOGRES_WORLD_CHAT_MIN_INTERVAL_SECONDS =
  2

/**
 * Untrusted client intent. The server derives identity from the session,
 * never from this payload.
 */
export interface LogresWorldChatIntent {
  body: string
}

/**
 * Server-owned chat message.
 */
export interface LogresWorldChatMessage {
  sequence: number
  senderUid: string
  body: string
  sentAtSeconds: number
  shardId: string
}

export interface LogresWorldChatRejection {
  accepted: false
  reason:
    | 'empty-body'
    | 'too-long'
    | 'rate-limited'
    | 'muted'
    | 'banned'
    | 'invalid-intent'
}

export interface LogresWorldChatAccepted {
  accepted: true
  message:
    Readonly<LogresWorldChatMessage>
  state: LogresWorldChatState
}

export type LogresWorldChatResult =
  | LogresWorldChatAccepted
  | LogresWorldChatRejection

export interface LogresWorldChatState {
  provenance:
    typeof LOGRES_WORLD_CHAT_PROVENANCE
  shardId: string
  messages:
    readonly Readonly<LogresWorldChatMessage>[]
  nextSequence: number
  /**
   * Last accepted send time per sender uid, used for rate limiting.
   */
  lastSentAtByUid:
    Readonly<
      Record<string, number>
    >
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

function freezeState(
  shardId: string,
  messages:
    readonly LogresWorldChatMessage[],
  nextSequence: number,
  lastSentAtByUid:
    Record<string, number>,
): LogresWorldChatState {
  return Object.freeze({
    provenance:
      LOGRES_WORLD_CHAT_PROVENANCE,
    shardId,
    messages:
      Object.freeze(
        messages.map(
          (m) =>
            Object.freeze({
              ...m,
            }),
        ),
      ),
    nextSequence,
    lastSentAtByUid:
      Object.freeze({
        ...lastSentAtByUid,
      }),
  })
}

/**
 * Creates a per-shard world-chat channel. The shard id must match the
 * active topology so a client cannot post into an arbitrary channel.
 */
export function createLogresWorldChatState(
  shardId: string,
): LogresWorldChatState {
  return freezeState(
    requireNonEmpty(
      shardId,
      'World-chat shardId',
    ),
    [],
    1,
    {},
  )
}

/**
 * Processes a client chat intent under server authority.
 *
 * The `senderUid` is the server-verified session uid; it is never taken
 * from the intent. The server enforces:
 * - intent shape
 * - non-empty, length-capped body
 * - per-sender rate limit
 * - active mute/ban sanctions from the moderation authority
 *
 * Rejections return a typed result rather than mutating state.
 */
export function submitLogresWorldChatIntent(
  state: LogresWorldChatState,
  moderation: LogresModerationState,
  senderUid: string,
  intent: LogresWorldChatIntent,
  nowSeconds: number,
): LogresWorldChatResult {
  if (
    state.provenance !==
    LOGRES_WORLD_CHAT_PROVENANCE
  ) {
    throw new Error(
      'World-chat provenance must be RECONSTRUCTED',
    )
  }

  const sender =
    requireNonEmpty(
      senderUid,
      'World-chat senderUid',
    )

  const now =
    requireSafeInteger(
      nowSeconds,
      'World-chat nowSeconds',
    )

  // Fail closed on a malformed intent object.
  if (
    typeof intent !== 'object' ||
    intent === null ||
    typeof intent.body !==
      'string'
  ) {
    return {
      accepted: false,
      reason:
        'invalid-intent',
    }
  }

  // Active ban rejects before any further processing.
  if (
    getActiveLogresSanction(
      moderation,
      sender,
      'ban',
      now,
    ) !== null
  ) {
    return {
      accepted: false,
      reason:
        'banned',
    }
  }

  // Active mute rejects before any further processing.
  if (
    getActiveLogresSanction(
      moderation,
      sender,
      'mute',
      now,
    ) !== null
  ) {
    return {
      accepted: false,
      reason:
        'muted',
    }
  }

  const body =
    intent.body.trim()

  if (!body) {
    return {
      accepted: false,
      reason:
        'empty-body',
    }
  }

  if (
    body.length >
    LOGRES_WORLD_CHAT_MAX_BODY_LENGTH
  ) {
    return {
      accepted: false,
      reason:
        'too-long',
    }
  }

  const lastSent =
    state.lastSentAtByUid[
      sender
    ]

  if (
    lastSent !==
      undefined &&
    now -
      lastSent <
      LOGRES_WORLD_CHAT_MIN_INTERVAL_SECONDS
  ) {
    return {
      accepted: false,
      reason:
        'rate-limited',
    }
  }

  const message:
    LogresWorldChatMessage = {
    sequence:
      state.nextSequence,
    senderUid: sender,
    body,
    sentAtSeconds: now,
    shardId:
      state.shardId,
  }

  const lastSentAtByUid = {
    ...state.lastSentAtByUid,
    [sender]: now,
  }

  return {
    accepted: true,
    message:
      Object.freeze(
        message,
      ),
    state:
      freezeState(
        state.shardId,
        [
          ...state.messages,
          message,
        ],
        state.nextSequence +
          1,
        lastSentAtByUid,
      ),
  }
}

/**
 * Reads the canonical server-owned message log.
 */
export function readLogresWorldChatLog(
  state: LogresWorldChatState,
): readonly Readonly<LogresWorldChatMessage>[] {
  if (
    state.provenance !==
    LOGRES_WORLD_CHAT_PROVENANCE
  ) {
    throw new Error(
      'World-chat provenance must be RECONSTRUCTED',
    )
  }

  return state.messages
}
