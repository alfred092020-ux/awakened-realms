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
