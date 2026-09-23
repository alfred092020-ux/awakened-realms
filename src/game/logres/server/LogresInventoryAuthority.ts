export const LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE =
  'RECONSTRUCTED' as const

export interface ReconstructedLogresInventoryEntry {
  /**
   * Reconstruction-local stable item identity.
   *
   * This is not claimed to be an original Logres item identifier.
   */
  itemKey: string

  /**
   * Original item identity remains nullable until recovered.
   */
  originalItemId:
    | string
    | null

  quantity: number

  grantKey: string
}

export interface ReconstructedLogresInventoryState {
  provenance:
    typeof LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE

  revision: number

  entries:
    readonly Readonly<
      ReconstructedLogresInventoryEntry
    >[]

  appliedGrantKeys:
    readonly string[]
}
export interface ReconstructedLogresRewardLineInput {
  itemKey: string

  originalItemId:
    | string
    | null

  quantity: number
}

export interface ReconstructedLogresInventoryGrantInput {
  /**
   * Reconstruction-local idempotency key supplied by the authoritative server.
   */
  grantKey: string

  entries:
    readonly ReconstructedLogresRewardLineInput[]
}

export interface ReconstructedLogresInventoryGrantResult {
  applied: boolean

  state:
    Readonly<
      ReconstructedLogresInventoryState
    >
}

function requireNonEmpty(
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
function requireOptionalOriginalId(
  value:
    | string
    | null,
): string | null {
  if (value === null) {
    return null
  }

  return requireNonEmpty(
    value,
    'Inventory originalItemId',
  )
}

function requirePositiveQuantity(
  value: number,
): number {
  if (
    !Number.isSafeInteger(
      value,
    ) ||
    value <= 0
  ) {
    throw new Error(
      'Inventory quantity must be a positive safe integer',
    )
  }

  return value
}

function freezeState(
  revision: number,
  entries:
    readonly ReconstructedLogresInventoryEntry[],
  appliedGrantKeys:
    readonly string[],
): Readonly<
  ReconstructedLogresInventoryState
> {
  return Object.freeze({
    provenance:
      LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE,
    revision,
    entries:
      Object.freeze(
        entries.map(
          (entry) =>
            Object.freeze({
              ...entry,
            }),
        ),
      ),
    appliedGrantKeys:
      Object.freeze([
        ...appliedGrantKeys,
      ]),
  })
}
/**
 * Empty replacement-server inventory state.
 *
 * RECONSTRUCTED only. The original client/server inventory packet schema,
 * capacities, stacking rules, equipment slots and historical item IDs remain
 * unresolved.
 */
export function createReconstructedLogresInventory():
  Readonly<
    ReconstructedLogresInventoryState
  > {
  return freezeState(
    0,
    [],
    [],
  )
}

/**
 * Applies one server-owned reward grant without inventing original inventory
 * semantics.
 *
 * RECONSTRUCTED contract:
 * - grantKey is a replacement-server idempotency key
 * - duplicate grantKey retries are no-ops
 * - reward lines are retained as grant ledger entries; they are not merged or
 *   stacked because original stacking semantics are unresolved
 * - originalItemId may remain null
 */
export function applyReconstructedLogresInventoryGrant(
  state:
    Readonly<
      ReconstructedLogresInventoryState
    >,
  input:
    ReconstructedLogresInventoryGrantInput,
): ReconstructedLogresInventoryGrantResult {
  if (
    state.provenance !==
    LOGRES_RECONSTRUCTED_INVENTORY_PROVENANCE
  ) {
    throw new Error(
      'Inventory state provenance must be RECONSTRUCTED',
    )
  }
  if (
    !Number.isSafeInteger(
      state.revision,
    ) ||
    state.revision < 0
  ) {
    throw new Error(
      'Inventory revision must be a non-negative safe integer',
    )
  }

  const grantKey =
    requireNonEmpty(
      input.grantKey,
      'Inventory grantKey',
    )

  if (
    state.appliedGrantKeys.includes(
      grantKey,
    )
  ) {
    return {
      applied:
        false,
      state,
    }
  }

  const seenItemKeys =
    new Set<string>()

  const additions =
    input.entries.map(
      (
        line,
      ) => {
        const itemKey =
          requireNonEmpty(
            line.itemKey,
            'Inventory itemKey',
          )

        if (
          seenItemKeys.has(
            itemKey,
          )
        ) {
          throw new Error(
            'Inventory grant itemKey entries must be unique',
          )
        }
        seenItemKeys.add(
          itemKey,
        )

        return {
          itemKey,
          originalItemId:
            requireOptionalOriginalId(
              line.originalItemId,
            ),
          quantity:
            requirePositiveQuantity(
              line.quantity,
            ),
          grantKey,
        }
      },
    )

  if (
    state.revision ===
    Number.MAX_SAFE_INTEGER
  ) {
    throw new Error(
      'Inventory revision exceeds safe integer range',
    )
  }

  return {
    applied:
      true,
    state:
      freezeState(
        state.revision +
          1,
        [
          ...state.entries,
          ...additions,
        ],
        [
          ...state.appliedGrantKeys,
          grantKey,
        ],
      ),
  }
}
