/*
 * Logical server topology.
 *
 * The production deployment starts with exactly three active shards. Future
 * shards may be activated or reconfigured server-side without requiring a
 * client rebuild: clients receive the shard directory at session bootstrap
 * and must never hardcode shard identity or count.
 *
 * This module fails closed: unknown shard ids, duplicate shard keys,
 * non-positive capacities, and deactivating below the minimum active-shard
 * floor all throw.
 */

export const LOGRES_SERVER_TOPOLOGY_PROVENANCE =
  'RECONSTRUCTED' as const

/**
 * Minimum number of simultaneously active shards. The deployment contract
 * starts at exactly three; operators may raise this floor but cannot go
 * below it.
 */
export const LOGRES_MIN_ACTIVE_SHARDS = 3

export interface LogresShardConfig {
  /**
   * Server-owned stable shard identity. Opaque to clients.
   */
  shardId: string

  /**
   * Human-readable label for diagnostics.
   */
  label: string

  /**
   * Maximum concurrent authenticated sessions this shard accepts.
   */
  sessionCapacity: number

  /**
   * Region/zone hint for placement; opaque routing metadata.
   */
  region: string
}

export interface LogresActiveShard
  extends LogresShardConfig {
  /**
   * Monotonic activation sequence, assigned server-side.
   */
  activationOrder: number
}

export interface LogresServerTopology {
  provenance:
    typeof LOGRES_SERVER_TOPOLOGY_PROVENANCE

  /**
   * Directory revision. Bumped on every topology change so clients can
   * detect staleness without a rebuild.
   */
  revision: number

  minActiveShards: number

  activeShards:
    readonly Readonly<LogresActiveShard>[]
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

function requirePositiveInteger(
  value: unknown,
  label: string,
): number {
  if (
    typeof value !== 'number' ||
    !Number.isSafeInteger(value) ||
    value <= 0
  ) {
    throw new Error(
      `${label} must be a positive safe integer`,
    )
  }

  return value
}

function validateShardConfig(
  config: LogresShardConfig,
): LogresShardConfig {
  return {
    shardId:
      requireNonEmpty(
        config.shardId,
        'Shard shardId',
      ),
    label:
      requireNonEmpty(
        config.label,
        'Shard label',
      ),
    sessionCapacity:
      requirePositiveInteger(
        config.sessionCapacity,
        'Shard sessionCapacity',
      ),
    region:
      requireNonEmpty(
        config.region,
        'Shard region',
      ),
  }
}

function freezeTopology(
  revision: number,
  minActiveShards: number,
  activeShards:
    readonly LogresActiveShard[],
): LogresServerTopology {
  if (
    activeShards.length <
    minActiveShards
  ) {
    throw new Error(
      'Active shard count is below the configured minimum',
    )
  }

  return Object.freeze({
    provenance:
      LOGRES_SERVER_TOPOLOGY_PROVENANCE,
    revision,
    minActiveShards,
    activeShards:
      Object.freeze(
        activeShards.map(
          (shard) =>
            Object.freeze({
              ...shard,
            }),
        ),
      ),
  })
}

/**
 * Creates the initial production topology with exactly three active shards.
 *
 * This is the deployment floor; additional shards can be activated later
 * via `activateLogresShard` without any client change.
 */
export function createInitialLogresServerTopology(
  shardConfigs: readonly [
    LogresShardConfig,
    LogresShardConfig,
    LogresShardConfig,
  ],
): LogresServerTopology {
  if (
    shardConfigs.length !==
    LOGRES_MIN_ACTIVE_SHARDS
  ) {
    throw new Error(
      'Initial topology requires exactly three shards',
    )
  }

  const seenIds =
    new Set<string>()

  const activeShards =
    shardConfigs.map(
      (config, index) => {
        const validated =
          validateShardConfig(
            config,
          )

        if (
          seenIds.has(
            validated.shardId,
          )
        ) {
          throw new Error(
            'Shard shardId must be unique',
          )
        }
        seenIds.add(
          validated.shardId,
        )

        return Object.freeze({
          ...validated,
          activationOrder:
            index + 1,
        })
      },
    )

  return freezeTopology(
    0,
    LOGRES_MIN_ACTIVE_SHARDS,
    activeShards,
  )
}

/**
 * Activates an additional shard without a client rebuild.
 *
 * Returns a new topology snapshot with a bumped revision so clients refresh
 * their shard directory. Duplicate shard ids fail closed.
 */
export function activateLogresShard(
  topology: LogresServerTopology,
  config: LogresShardConfig,
): LogresServerTopology {
  if (
    topology.provenance !==
    LOGRES_SERVER_TOPOLOGY_PROVENANCE
  ) {
    throw new Error(
      'Topology provenance must be RECONSTRUCTED',
    )
  }

  const validated =
    validateShardConfig(
      config,
    )

  if (
    topology.activeShards.some(
      (shard) =>
        shard.shardId ===
        validated.shardId,
    )
  ) {
    throw new Error(
      'Shard shardId is already active',
    )
  }

  const nextOrder =
    topology.activeShards.length +
    1

  return freezeTopology(
    topology.revision + 1,
    topology.minActiveShards,
    [
      ...topology.activeShards,
      Object.freeze({
        ...validated,
        activationOrder:
          nextOrder,
      }),
    ],
  )
}

/**
 * Deactivates a shard. Fails closed if removal would drop below the
 * configured minimum active-shard floor.
 */
export function deactivateLogresShard(
  topology: LogresServerTopology,
  shardId: string,
): LogresServerTopology {
  if (
    topology.provenance !==
    LOGRES_SERVER_TOPOLOGY_PROVENANCE
  ) {
    throw new Error(
      'Topology provenance must be RECONSTRUCTED',
    )
  }

  const target =
    requireNonEmpty(
      shardId,
      'Shard shardId',
    )

  const existing =
    topology.activeShards.find(
      (shard) =>
        shard.shardId ===
        target,
    )

  if (!existing) {
    throw new Error(
      'Shard shardId is not active',
    )
  }

  if (
    topology.activeShards.length -
      1 <
    topology.minActiveShards
  ) {
    throw new Error(
      'Cannot deactivate below the minimum active shard count',
    )
  }

  return freezeTopology(
    topology.revision + 1,
    topology.minActiveShards,
    topology.activeShards.filter(
      (shard) =>
        shard.shardId !==
        target,
    ),
  )
}

/**
 * Resolves the shard an authenticated session is routed to.
 *
 * Fails closed: an unknown or inactive shard id throws rather than silently
 * falling back.
 */
export function resolveLogresSessionShard(
  topology: LogresServerTopology,
  shardId: string,
): Readonly<LogresActiveShard> {
  if (
    topology.provenance !==
    LOGRES_SERVER_TOPOLOGY_PROVENANCE
  ) {
    throw new Error(
      'Topology provenance must be RECONSTRUCTED',
    )
  }

  const target =
    requireNonEmpty(
      shardId,
      'Shard shardId',
    )

  const shard =
    topology.activeShards.find(
      (candidate) =>
        candidate.shardId ===
        target,
    )

  if (!shard) {
    throw new Error(
      'Requested shard is not active',
    )
  }

  return shard
}
