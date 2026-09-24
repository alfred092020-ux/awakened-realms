import type {
  ReconstructedLogresQuestInstance,
} from '../server/LogresQuestInstanceAuthority'
import {
  LOGRES_GLOBAL_3024_QUESTS,
  LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED,
} from './LogresGlobal3024SystemsEvidence'

export const LOGRES_QUEST_RUNTIME_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY' as const

export type LogresQuestPhase =
  | 'AVAILABLE'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'REWARDED'
  | 'RETIRED'

export interface LogresAuthenticatedQuestSession {
  readonly accountId: string
  readonly sessionId: string
  readonly authenticated: boolean
}

export interface LogresQuestRewardRecord {
  readonly rewardKey: string
  readonly originalItemId: string | null
  readonly quantity: number | null
  readonly currencyAmount: number | null
}

export interface LogresQuestProgressRecord {
  readonly provenance:
    typeof LOGRES_QUEST_RUNTIME_PROVENANCE
  readonly accountId: string
  readonly instance:
    Readonly<ReconstructedLogresQuestInstance>
  readonly phase: LogresQuestPhase
  readonly progressByObjective:
    Readonly<Record<string, number>>
  readonly reward:
    Readonly<LogresQuestRewardRecord> | null
  readonly appliedCommandIds:
    readonly string[]
  readonly revision: number
}

export interface LogresQuestPersistence {
  load(
    accountId: string,
    instanceKey: string,
  ): LogresQuestProgressRecord | null

  save(
    record: LogresQuestProgressRecord,
  ): void
}

export const LOGRES_QUEST_RUNTIME_EVIDENCE =
  Object.freeze({
    acceptRequest:
      LOGRES_GLOBAL_3024_QUESTS
        .requests.accept,
    retireRequest:
      LOGRES_GLOBAL_3024_QUESTS
        .requests.retire,
    serverStatePushSequence:
      LOGRES_GLOBAL_3024_QUESTS
        .statePushSequence,
    authorityInterpretation:
      LOGRES_GLOBAL_3024_QUESTS
        .authorityInterpretation,
    unresolvedHistoricalPayloads:
      LOGRES_GLOBAL_3024_SYSTEMS_UNRESOLVED
        .filter((entry) =>
          entry.includes('quest'),
        ),
  })

function requireIdentity(
  value: string,
  label: string,
): string {
  const normalized = value.trim()
  if (!normalized) {
    throw new Error(
      `${label} must be non-empty`,
    )
  }
  return normalized
}

function requireSession(
  session: LogresAuthenticatedQuestSession,
): {
  accountId: string
  sessionId: string
} {
  if (!session.authenticated) {
    throw new Error(
      'Quest mutation requires an authenticated session',
    )
  }

  return {
    accountId:
      requireIdentity(
        session.accountId,
        'Quest accountId',
      ),
    sessionId:
      requireIdentity(
        session.sessionId,
        'Quest sessionId',
      ),
  }
}

function cloneReward(
  reward:
    | Readonly<LogresQuestRewardRecord>
    | null,
): Readonly<LogresQuestRewardRecord> | null {
  if (reward === null) {
    return null
  }
  return Object.freeze({
    rewardKey: reward.rewardKey,
    originalItemId:
      reward.originalItemId,
    quantity: reward.quantity,
    currencyAmount:
      reward.currencyAmount,
  })
}

function cloneRecord(
  record: LogresQuestProgressRecord,
): LogresQuestProgressRecord {
  return Object.freeze({
    provenance:
      LOGRES_QUEST_RUNTIME_PROVENANCE,
    accountId: record.accountId,
    instance: record.instance,
    phase: record.phase,
    progressByObjective:
      Object.freeze({
        ...record.progressByObjective,
      }),
    reward:
      cloneReward(record.reward),
    appliedCommandIds:
      Object.freeze([
        ...record.appliedCommandIds,
      ]),
    revision: record.revision,
  })
}

function hasCommand(
  record: LogresQuestProgressRecord,
  commandId: string,
): boolean {
  return record.appliedCommandIds
    .includes(commandId)
}

function withCommand(
  record: LogresQuestProgressRecord,
  commandId: string,
  patch:
    Partial<
      Pick<
        LogresQuestProgressRecord,
        | 'phase'
        | 'progressByObjective'
        | 'reward'
      >
    >,
): LogresQuestProgressRecord {
  return cloneRecord({
    ...record,
    ...patch,
    appliedCommandIds: [
      ...record.appliedCommandIds,
      commandId,
    ],
    revision:
      record.revision + 1,
  })
}

function requireCommandId(
  commandId: string,
): string {
  return requireIdentity(
    commandId,
    'Quest commandId',
  )
}

function requireNonNegativeSafeInteger(
  value: number,
  label: string,
): number {
  if (
    !Number.isSafeInteger(value) ||
    value < 0
  ) {
    throw new Error(
      `${label} must be a non-negative safe integer`,
    )
  }
  return value
}

function validateReward(
  reward: LogresQuestRewardRecord,
): Readonly<LogresQuestRewardRecord> {
  const rewardKey =
    requireIdentity(
      reward.rewardKey,
      'Quest rewardKey',
    )

  const quantity =
    reward.quantity === null
      ? null
      : requireNonNegativeSafeInteger(
          reward.quantity,
          'Quest reward quantity',
        )

  const currencyAmount =
    reward.currencyAmount === null
      ? null
      : requireNonNegativeSafeInteger(
          reward.currencyAmount,
          'Quest reward currencyAmount',
        )

  const originalItemId =
    reward.originalItemId === null
      ? null
      : requireIdentity(
          reward.originalItemId,
          'Quest originalItemId',
        )

  return Object.freeze({
    rewardKey,
    originalItemId,
    quantity,
    currencyAmount,
  })
}

export class InMemoryLogresQuestPersistence
  implements LogresQuestPersistence {
  private readonly records =
    new Map<string, LogresQuestProgressRecord>()

  private key(
    accountId: string,
    instanceKey: string,
  ): string {
    return `${accountId}::${instanceKey}`
  }

  load(
    accountId: string,
    instanceKey: string,
  ): LogresQuestProgressRecord | null {
    const record =
      this.records.get(
        this.key(
          accountId,
          instanceKey,
        ),
      )

    return record
      ? cloneRecord(record)
      : null
  }

  save(
    record: LogresQuestProgressRecord,
  ): void {
    this.records.set(
      this.key(
        record.accountId,
        record.instance.instanceKey,
      ),
      cloneRecord(record),
    )
  }
}

export class LogresQuestAuthority {
  private readonly persistence:
    LogresQuestPersistence

  constructor(
    persistence:
      LogresQuestPersistence,
  ) {
    this.persistence = persistence
  }

  read(
    session:
      LogresAuthenticatedQuestSession,
    instanceKey: string,
  ): LogresQuestProgressRecord | null {
    const identity =
      requireSession(session)

    return this.persistence.load(
      identity.accountId,
      requireIdentity(
        instanceKey,
        'Quest instanceKey',
      ),
    )
  }

  accept(
    session:
      LogresAuthenticatedQuestSession,
    instance:
      Readonly<ReconstructedLogresQuestInstance>,
    commandId: string,
  ): LogresQuestProgressRecord {
    const identity =
      requireSession(session)
    const command =
      requireCommandId(commandId)

    const current =
      this.persistence.load(
        identity.accountId,
        instance.instanceKey,
      )

    if (current) {
      if (hasCommand(current, command)) {
        return current
      }
      throw new Error(
        'Quest instance is already accepted for this account',
      )
    }

    const progress:
      Record<string, number> = {}

    for (
      const objectiveId of
      instance.objectiveIds
    ) {
      progress[objectiveId] = 0
    }

    const record =
      cloneRecord({
        provenance:
          LOGRES_QUEST_RUNTIME_PROVENANCE,
        accountId:
          identity.accountId,
        instance,
        phase:
          'IN_PROGRESS',
        progressByObjective:
          Object.freeze(progress),
        reward: null,
        appliedCommandIds:
          Object.freeze([command]),
        revision: 1,
      })

    this.persistence.save(record)
    return record
  }

  progress(
    session:
      LogresAuthenticatedQuestSession,
    instanceKey: string,
    objectiveId: string,
    delta: number,
    commandId: string,
  ): LogresQuestProgressRecord {
    const identity =
      requireSession(session)
    const key =
      requireIdentity(
        instanceKey,
        'Quest instanceKey',
      )
    const objective =
      requireIdentity(
        objectiveId,
        'Quest objectiveId',
      )
    const amount =
      requireNonNegativeSafeInteger(
        delta,
        'Quest progress delta',
      )
    const command =
      requireCommandId(commandId)

    const current =
      this.persistence.load(
        identity.accountId,
        key,
      )

    if (!current) {
      throw new Error(
        'Quest instance must be accepted before progress',
      )
    }

    if (hasCommand(current, command)) {
      return current
    }

    if (
      current.phase !==
      'IN_PROGRESS'
    ) {
      throw new Error(
        'Quest progress is only valid while IN_PROGRESS',
      )
    }

    if (
      !current.instance.objectiveIds
        .includes(objective)
    ) {
      throw new Error(
        'Quest objective is not part of this instance',
      )
    }

    const next =
      withCommand(
        current,
        command,
        {
          progressByObjective:
            Object.freeze({
              ...current
                .progressByObjective,
              [objective]:
                current
                  .progressByObjective[
                    objective
                  ] + amount,
            }),
        },
      )

    this.persistence.save(next)
    return next
  }

  complete(
    session:
      LogresAuthenticatedQuestSession,
    instanceKey: string,
    commandId: string,
  ): LogresQuestProgressRecord {
    const identity =
      requireSession(session)
    const key =
      requireIdentity(
        instanceKey,
        'Quest instanceKey',
      )
    const command =
      requireCommandId(commandId)
    const current =
      this.persistence.load(
        identity.accountId,
        key,
      )

    if (!current) {
      throw new Error(
        'Quest instance must be accepted before completion',
      )
    }

    if (hasCommand(current, command)) {
      return current
    }

    if (
      current.phase !==
      'IN_PROGRESS'
    ) {
      throw new Error(
        'Quest completion is only valid while IN_PROGRESS',
      )
    }

    const next =
      withCommand(
        current,
        command,
        {
          phase:
            'COMPLETED',
        },
      )

    this.persistence.save(next)
    return next
  }

  grantReward(
    session:
      LogresAuthenticatedQuestSession,
    instanceKey: string,
    reward:
      LogresQuestRewardRecord,
    commandId: string,
  ): LogresQuestProgressRecord {
    const identity =
      requireSession(session)
    const key =
      requireIdentity(
        instanceKey,
        'Quest instanceKey',
      )
    const command =
      requireCommandId(commandId)
    const current =
      this.persistence.load(
        identity.accountId,
        key,
      )

    if (!current) {
      throw new Error(
        'Quest instance must exist before reward',
      )
    }

    if (hasCommand(current, command)) {
      return current
    }

    if (
      current.phase !==
      'COMPLETED'
    ) {
      throw new Error(
        'Quest reward is only valid after completion',
      )
    }

    const next =
      withCommand(
        current,
        command,
        {
          phase:
            'REWARDED',
          reward:
            validateReward(reward),
        },
      )

    this.persistence.save(next)
    return next
  }

  retire(
    session:
      LogresAuthenticatedQuestSession,
    instanceKey: string,
    commandId: string,
  ): LogresQuestProgressRecord {
    const identity =
      requireSession(session)
    const key =
      requireIdentity(
        instanceKey,
        'Quest instanceKey',
      )
    const command =
      requireCommandId(commandId)
    const current =
      this.persistence.load(
        identity.accountId,
        key,
      )

    if (!current) {
      throw new Error(
        'Quest instance must exist before retire',
      )
    }

    if (hasCommand(current, command)) {
      return current
    }

    if (
      current.phase === 'REWARDED' ||
      current.phase === 'RETIRED'
    ) {
      throw new Error(
        'Quest cannot retire after terminal resolution',
      )
    }

    const next =
      withCommand(
        current,
        command,
        {
          phase:
            'RETIRED',
        },
      )

    this.persistence.save(next)
    return next
  }
}
