import {
  createReconstructedLogresInventory,
  LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE,
  type ReconstructedLogresInventoryState,
} from './LogresInventoryAuthority'
import {
  LOGRES_QUEST_RUNTIME_PROVENANCE,
  type LogresQuestPersistence,
  type LogresQuestProgressRecord,
} from '../systems/LogresQuestRuntime'

export const LOGRES_PERSISTENCE_RECOVERY_PROVENANCE =
  'RECONSTRUCTED_SERVER_AUTHORITY' as const

export const LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION =
  1 as const

export interface LogresPersistenceBackingStore {
  read(accountId: string): string | null
  write(accountId: string, serialized: string): void
}

export interface LogresPersistenceRecoverySnapshot<
  TProgression extends object = Record<string, unknown>,
  TSession extends object = Record<string, unknown>,
> {
  readonly provenance:
    typeof LOGRES_PERSISTENCE_RECOVERY_PROVENANCE
  readonly schemaVersion:
    typeof LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION
  readonly accountId: string
  readonly revision: number
  readonly progression: TProgression | null
  readonly quests:
    readonly Readonly<LogresQuestProgressRecord>[]
  readonly inventory:
    Readonly<ReconstructedLogresInventoryState>
  readonly session: TSession | null
  readonly appliedCheckpointIds:
    readonly string[]
}

export interface LogresPersistenceCheckpointInput<
  TProgression extends object = Record<string, unknown>,
  TSession extends object = Record<string, unknown>,
> {
  readonly checkpointId: string
  readonly progression?: TProgression | null
  readonly quests?:
    readonly LogresQuestProgressRecord[]
  readonly inventory?:
    Readonly<ReconstructedLogresInventoryState>
  readonly session?: TSession | null
}

export class InMemoryLogresPersistenceBackingStore
  implements LogresPersistenceBackingStore {
  private readonly records =
    new Map<string, string>()

  read(accountId: string): string | null {
    return this.records.get(
      requireIdentity(
        accountId,
        'Persistence accountId',
      ),
    ) ?? null
  }

  write(
    accountId: string,
    serialized: string,
  ): void {
    const key =
      requireIdentity(
        accountId,
        'Persistence accountId',
      )

    if (!serialized) {
      throw new Error(
        'Persistence serialized snapshot must be non-empty',
      )
    }

    this.records.set(
      key,
      serialized,
    )
  }
}

function requireIdentity(
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

function requireRevision(
  value: unknown,
  label: string,
): number {
  if (
    !Number.isSafeInteger(value) ||
    (value as number) < 0
  ) {
    throw new Error(
      `${label} must be a non-negative safe integer`,
    )
  }

  return value as number
}

function assertJsonSafe(
  value: unknown,
  label: string,
  seen = new Set<object>(),
): void {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'boolean'
  ) {
    return
  }

  if (typeof value === 'number') {
    if (!Number.isFinite(value)) {
      throw new Error(
        `${label} contains a non-finite number`,
      )
    }
    return
  }

  if (typeof value !== 'object') {
    throw new Error(
      `${label} must contain only JSON-safe values`,
    )
  }

  if (seen.has(value)) {
    throw new Error(
      `${label} must not contain cycles`,
    )
  }

  const prototype =
    Object.getPrototypeOf(value)

  if (
    !Array.isArray(value) &&
    prototype !== Object.prototype &&
    prototype !== null
  ) {
    throw new Error(
      `${label} must contain only plain objects and arrays`,
    )
  }

  seen.add(value)

  for (
    const [key, entry] of
    Object.entries(value)
  ) {
    assertJsonSafe(
      entry,
      `${label}.${key}`,
      seen,
    )
  }

  seen.delete(value)
}

function deepFreeze<T>(value: T): T {
  if (
    value !== null &&
    typeof value === 'object' &&
    !Object.isFrozen(value)
  ) {
    for (
      const entry of
      Object.values(
        value as Record<string, unknown>,
      )
    ) {
      deepFreeze(entry)
    }

    Object.freeze(value)
  }

  return value
}

function cloneJson<T>(
  value: T,
  label: string,
): T {
  assertJsonSafe(
    value,
    label,
  )

  return deepFreeze(
    JSON.parse(
      JSON.stringify(value),
    ) as T,
  )
}

function requireStringArray(
  value: unknown,
  label: string,
): readonly string[] {
  if (!Array.isArray(value)) {
    throw new Error(
      `${label} must be an array`,
    )
  }

  const seen =
    new Set<string>()

  const normalized =
    value.map(
      (entry) => {
        if (typeof entry !== 'string') {
          throw new Error(
            `${label} entries must be strings`,
          )
        }

        const item =
          requireIdentity(
            entry,
            `${label} entry`,
          )

        if (seen.has(item)) {
          throw new Error(
            `${label} entries must be unique`,
          )
        }

        seen.add(item)
        return item
      },
    )

  return Object.freeze(
    normalized,
  )
}

function cloneSlice<T extends object>(
  value: unknown,
  label: string,
): T | null {
  if (value === null) {
    return null
  }

  if (
    typeof value !== 'object' ||
    Array.isArray(value)
  ) {
    throw new Error(
      `${label} must be null or a JSON object`,
    )
  }

  return cloneJson(
    value as T,
    label,
  )
}

function optionalRevision(
  value: object | null,
): number | null {
  if (
    value === null ||
    !Object.prototype
      .hasOwnProperty.call(
        value,
        'revision',
      )
  ) {
    return null
  }

  return requireRevision(
    (
      value as Record<string, unknown>
    ).revision,
    'Persistent slice revision',
  )
}

function assertMonotonicSlice(
  current: object | null,
  next: object | null,
  label: string,
): void {
  if (
    current === null ||
    next === null
  ) {
    return
  }

  const currentRevision =
    optionalRevision(current)
  const nextRevision =
    optionalRevision(next)

  if (
    currentRevision === null ||
    nextRevision === null
  ) {
    return
  }

  if (nextRevision < currentRevision) {
    throw new Error(
      `${label} revision cannot move backwards`,
    )
  }

  if (
    nextRevision === currentRevision &&
    JSON.stringify(next) !==
      JSON.stringify(current)
  ) {
    throw new Error(
      `${label} cannot replace the same revision with different state`,
    )
  }
}

function validateInventory(
  value: unknown,
): Readonly<ReconstructedLogresInventoryState> {
  if (
    value === null ||
    typeof value !== 'object' ||
    Array.isArray(value)
  ) {
    throw new Error(
      'Persistence inventory snapshot must be an object',
    )
  }

  const inventory =
    value as Record<string, unknown>

  if (
    inventory.provenance !==
    LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE
  ) {
    throw new Error(
      'Persistence inventory provenance must be RECONSTRUCTED',
    )
  }

  requireRevision(
    inventory.revision,
    'Persistence inventory revision',
  )

  const grantKeys =
    requireStringArray(
      inventory.appliedGrantKeys,
      'Persistence inventory appliedGrantKeys',
    )

  if (!Array.isArray(inventory.entries)) {
    throw new Error(
      'Persistence inventory entries must be an array',
    )
  }

  for (const raw of inventory.entries) {
    if (
      raw === null ||
      typeof raw !== 'object'
    ) {
      throw new Error(
        'Persistence inventory entries must be objects',
      )
    }

    const grantKey =
      (raw as Record<string, unknown>)
        .grantKey

    if (
      typeof grantKey !== 'string' ||
      !grantKeys.includes(grantKey)
    ) {
      throw new Error(
        'Persistence inventory entry references an unapplied grant',
      )
    }
  }

  return cloneJson(
    inventory,
    'Persistence inventory',
  ) as unknown as
    Readonly<ReconstructedLogresInventoryState>
}

function validateQuestRecord(
  value: unknown,
  accountId: string,
): Readonly<LogresQuestProgressRecord> {
  if (
    value === null ||
    typeof value !== 'object' ||
    Array.isArray(value)
  ) {
    throw new Error(
      'Persistence quest record must be an object',
    )
  }

  const record =
    value as Record<string, unknown>

  if (
    record.provenance !==
    LOGRES_QUEST_RUNTIME_PROVENANCE
  ) {
    throw new Error(
      'Persistence quest provenance is invalid',
    )
  }

  if (record.accountId !== accountId) {
    throw new Error(
      'Persistence quest accountId does not match snapshot account',
    )
  }

  requireRevision(
    record.revision,
    'Persistence quest revision',
  )

  const instance =
    record.instance

  if (
    instance === null ||
    typeof instance !== 'object' ||
    Array.isArray(instance) ||
    typeof (
      instance as Record<string, unknown>
    ).instanceKey !== 'string'
  ) {
    throw new Error(
      'Persistence quest instance is invalid',
    )
  }

  requireIdentity(
    (
      instance as Record<string, string>
    ).instanceKey,
    'Persistence quest instanceKey',
  )

  requireStringArray(
    record.appliedCommandIds,
    'Persistence quest appliedCommandIds',
  )

  return cloneJson(
    record,
    'Persistence quest',
  ) as unknown as
    Readonly<LogresQuestProgressRecord>
}

function validateQuestList(
  value: unknown,
  accountId: string,
): readonly Readonly<LogresQuestProgressRecord>[] {
  if (!Array.isArray(value)) {
    throw new Error(
      'Persistence quests must be an array',
    )
  }

  const seen =
    new Set<string>()

  const records =
    value.map(
      (entry) => {
        const record =
          validateQuestRecord(
            entry,
            accountId,
          )
        const key =
          record.instance
            .instanceKey

        if (seen.has(key)) {
          throw new Error(
            'Persistence quest instance keys must be unique',
          )
        }

        seen.add(key)
        return record
      },
    )

  return Object.freeze(
    records,
  )
}

function validateInventoryTransition(
  current:
    Readonly<ReconstructedLogresInventoryState>,
  next:
    Readonly<ReconstructedLogresInventoryState>,
): void {
  if (
    next.revision <
    current.revision
  ) {
    throw new Error(
      'Persistence inventory revision cannot move backwards',
    )
  }

  if (
    next.revision ===
      current.revision &&
    JSON.stringify(next) !==
      JSON.stringify(current)
  ) {
    throw new Error(
      'Persistence inventory cannot replace the same revision with different state',
    )
  }

  for (
    const grantKey of
    current.appliedGrantKeys
  ) {
    if (
      !next.appliedGrantKeys
        .includes(grantKey)
    ) {
      throw new Error(
        'Persistence inventory cannot discard an applied grant key',
      )
    }
  }
}

function validateQuestTransitions(
  current:
    readonly Readonly<LogresQuestProgressRecord>[],
  next:
    readonly Readonly<LogresQuestProgressRecord>[],
): void {
  const nextByKey =
    new Map(
      next.map(
        (record) => [
          record.instance
            .instanceKey,
          record,
        ],
      ),
    )

  for (const previous of current) {
    const candidate =
      nextByKey.get(
        previous.instance
          .instanceKey,
      )

    if (!candidate) {
      throw new Error(
        'Persistence quest history cannot discard an existing instance',
      )
    }

    if (
      candidate.revision <
      previous.revision
    ) {
      throw new Error(
        'Persistence quest revision cannot move backwards',
      )
    }

    if (
      candidate.revision ===
        previous.revision &&
      JSON.stringify(candidate) !==
        JSON.stringify(previous)
    ) {
      throw new Error(
        'Persistence quest cannot replace the same revision with different state',
      )
    }
  }
}

function createEmptySnapshot(
  accountId: string,
): LogresPersistenceRecoverySnapshot {
  return Object.freeze({
    provenance:
      LOGRES_PERSISTENCE_RECOVERY_PROVENANCE,
    schemaVersion:
      LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION,
    accountId,
    revision: 0,
    progression: null,
    quests:
      Object.freeze([]),
    inventory:
      createReconstructedLogresInventory(),
    session: null,
    appliedCheckpointIds:
      Object.freeze([]),
  })
}

function parseSnapshot<
  TProgression extends object,
  TSession extends object,
>(
  serialized: string,
  accountId: string,
): LogresPersistenceRecoverySnapshot<
  TProgression,
  TSession
> {
  let raw: unknown

  try {
    raw =
      JSON.parse(serialized)
  } catch {
    throw new Error(
      'Persistence snapshot is not valid JSON',
    )
  }

  if (
    raw === null ||
    typeof raw !== 'object' ||
    Array.isArray(raw)
  ) {
    throw new Error(
      'Persistence snapshot must be an object',
    )
  }

  const snapshot =
    raw as Record<string, unknown>

  if (
    snapshot.provenance !==
    LOGRES_PERSISTENCE_RECOVERY_PROVENANCE
  ) {
    throw new Error(
      'Persistence snapshot provenance is invalid',
    )
  }

  if (
    snapshot.schemaVersion !==
    LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION
  ) {
    throw new Error(
      'Persistence snapshot schema version is unsupported',
    )
  }

  if (snapshot.accountId !== accountId) {
    throw new Error(
      'Persistence snapshot accountId does not match requested account',
    )
  }

  return Object.freeze({
    provenance:
      LOGRES_PERSISTENCE_RECOVERY_PROVENANCE,
    schemaVersion:
      LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION,
    accountId,
    revision:
      requireRevision(
        snapshot.revision,
        'Persistence snapshot revision',
      ),
    progression:
      cloneSlice<TProgression>(
        snapshot.progression,
        'Persistence progression',
      ),
    quests:
      validateQuestList(
        snapshot.quests,
        accountId,
      ),
    inventory:
      validateInventory(
        snapshot.inventory,
      ),
    session:
      cloneSlice<TSession>(
        snapshot.session,
        'Persistence session',
      ),
    appliedCheckpointIds:
      requireStringArray(
        snapshot
          .appliedCheckpointIds,
        'Persistence appliedCheckpointIds',
      ),
  })
}

/**
 * Reconstructed persistence/recovery boundary.
 *
 * It stores replacement-server snapshots only. It does not claim the original
 * Logres storage engine, database schema, reconnect packet, or transaction
 * model.
 */
export class LogresPersistenceRecovery {
  private readonly backing:
    LogresPersistenceBackingStore

  constructor(
    backing:
      LogresPersistenceBackingStore =
        new InMemoryLogresPersistenceBackingStore(),
  ) {
    this.backing = backing
  }

  recover<
    TProgression extends object =
      Record<string, unknown>,
    TSession extends object =
      Record<string, unknown>,
  >(
    accountId: string,
  ):
    | LogresPersistenceRecoverySnapshot<
        TProgression,
        TSession
      >
    | null {
    const account =
      requireIdentity(
        accountId,
        'Persistence accountId',
      )
    const serialized =
      this.backing.read(account)

    if (serialized === null) {
      return null
    }

    return parseSnapshot<
      TProgression,
      TSession
    >(
      serialized,
      account,
    )
  }

  checkpoint<
    TProgression extends object =
      Record<string, unknown>,
    TSession extends object =
      Record<string, unknown>,
  >(
    accountId: string,
    input:
      LogresPersistenceCheckpointInput<
        TProgression,
        TSession
      >,
  ): LogresPersistenceRecoverySnapshot<
    TProgression,
    TSession
  > {
    const account =
      requireIdentity(
        accountId,
        'Persistence accountId',
      )
    const checkpointId =
      requireIdentity(
        input.checkpointId,
        'Persistence checkpointId',
      )
    const current =
      this.recover<
        TProgression,
        TSession
      >(account) ??
      (
        createEmptySnapshot(
          account,
        ) as
          LogresPersistenceRecoverySnapshot<
            TProgression,
            TSession
          >
      )

    if (
      current.appliedCheckpointIds
        .includes(checkpointId)
    ) {
      return current
    }

    const progression =
      input.progression === undefined
        ? current.progression
        : cloneSlice<TProgression>(
            input.progression,
            'Persistence progression',
          )
    const session =
      input.session === undefined
        ? current.session
        : cloneSlice<TSession>(
            input.session,
            'Persistence session',
          )

    assertMonotonicSlice(
      current.progression,
      progression,
      'Persistence progression',
    )
    assertMonotonicSlice(
      current.session,
      session,
      'Persistence session',
    )

    const quests =
      input.quests === undefined
        ? current.quests
        : validateQuestList(
            input.quests,
            account,
          )
    validateQuestTransitions(
      current.quests,
      quests,
    )

    const inventory =
      input.inventory === undefined
        ? current.inventory
        : validateInventory(
            input.inventory,
          )
    validateInventoryTransition(
      current.inventory,
      inventory,
    )

    if (
      current.revision ===
      Number.MAX_SAFE_INTEGER
    ) {
      throw new Error(
        'Persistence snapshot revision exceeds safe integer range',
      )
    }

    const next =
      Object.freeze({
        provenance:
          LOGRES_PERSISTENCE_RECOVERY_PROVENANCE,
        schemaVersion:
          LOGRES_PERSISTENCE_RECOVERY_SCHEMA_VERSION,
        accountId: account,
        revision:
          current.revision + 1,
        progression,
        quests,
        inventory,
        session,
        appliedCheckpointIds:
          Object.freeze([
            ...current
              .appliedCheckpointIds,
            checkpointId,
          ]),
      }) satisfies
        LogresPersistenceRecoverySnapshot<
          TProgression,
          TSession
        >

    const serialized =
      JSON.stringify(next)

    this.backing.write(
      account,
      serialized,
    )

    return parseSnapshot<
      TProgression,
      TSession
    >(
      serialized,
      account,
    )
  }

  saveProgression<
    TProgression extends object,
  >(
    accountId: string,
    progression: TProgression,
    checkpointId: string,
  ): LogresPersistenceRecoverySnapshot<
    TProgression,
    Record<string, unknown>
  > {
    return this.checkpoint(
      accountId,
      {
        checkpointId,
        progression,
      },
    )
  }

  saveSession<
    TSession extends object,
  >(
    accountId: string,
    session: TSession,
    checkpointId: string,
  ): LogresPersistenceRecoverySnapshot<
    Record<string, unknown>,
    TSession
  > {
    return this.checkpoint(
      accountId,
      {
        checkpointId,
        session,
      },
    )
  }

  saveInventory(
    accountId: string,
    inventory:
      Readonly<ReconstructedLogresInventoryState>,
    checkpointId: string,
  ): LogresPersistenceRecoverySnapshot {
    return this.checkpoint(
      accountId,
      {
        checkpointId,
        inventory,
      },
    )
  }

  saveQuestRecord(
    record:
      LogresQuestProgressRecord,
  ): LogresPersistenceRecoverySnapshot {
    const account =
      requireIdentity(
        record.accountId,
        'Persistence quest accountId',
      )
    const current =
      this.recover(account) ??
      createEmptySnapshot(account)
    const key =
      requireIdentity(
        record.instance
          .instanceKey,
        'Persistence quest instanceKey',
      )
    const quests = [
      ...current.quests.filter(
        (candidate) =>
          candidate.instance
            .instanceKey !==
          key,
      ),
      record,
    ]

    return this.checkpoint(
      account,
      {
        checkpointId:
          `quest:${key}:revision:${record.revision}`,
        quests,
      },
    )
  }

  createQuestPersistence(
    accountId: string,
  ): LogresQuestPersistence {
    const account =
      requireIdentity(
        accountId,
        'Persistence quest accountId',
      )

    return {
      load: (
        requestedAccountId:
          string,
        instanceKey:
          string,
      ) => {
        if (
          requireIdentity(
            requestedAccountId,
            'Persistence quest accountId',
          ) !== account
        ) {
          throw new Error(
            'Quest persistence adapter is account-scoped',
          )
        }

        const key =
          requireIdentity(
            instanceKey,
            'Persistence quest instanceKey',
          )
        const snapshot =
          this.recover(account)
        const record =
          snapshot?.quests.find(
            (candidate) =>
              candidate.instance
                .instanceKey ===
              key,
          )

        return record
          ? cloneJson(
              record,
              'Persistence quest',
            )
          : null
      },
      save: (
        record:
          LogresQuestProgressRecord,
      ) => {
        if (
          record.accountId !==
          account
        ) {
          throw new Error(
            'Quest persistence adapter rejected a different account',
          )
        }

        this.saveQuestRecord(record)
      },
    }
  }
}
