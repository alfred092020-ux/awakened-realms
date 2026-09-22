import type {
  LogresFieldNavigationLookup,
  LogresFieldNavigationTile,
} from './LogresFieldNavigation'
import {
  createLogresFieldNavigationTile,
} from './LogresFieldNavigation'
import {
  createLogresFieldGridIndex,
} from './LogresFieldGridIndex'
import type {
  LogresMapGrid,
  LogresMapRoot,
} from './LogresMapBinary'
import {
  logresMapSafeInt,
} from './LogresMapBinary'
import type {
  LogresMapInfoTable,
} from './LogresMapInfoBinary'
import {
  logresMapInfoHeight,
} from './LogresMapInfoBinary'

export const LOGRES_FIELD_LEVEL_FORMULA_EVIDENCE =
  'CONFIRMED_ORIGINAL_CURRENT_JP_NATIVE' as const

export const LOGRES_GLOBAL_FIELD_LEVEL_APPLICATION =
  'SUPPORTED_INFERENCE' as const

export interface LogresFieldBlockLevelEvidence {
  level: number
  resolvedBlockCount: number
  unresolvedPackedChipIds:
    readonly number[]
}

export interface LogresFieldNavigationModel {
  /**
   * Current-JP native formula is directly recovered.
   *
   * Applying the same formula to May-2017 Global remains SUPPORTED INFERENCE
   * until the original Global field-level functions are recovered again.
   */
  formulaEvidence:
    typeof LOGRES_FIELD_LEVEL_FORMULA_EVIDENCE

  globalTargetApplication:
    typeof LOGRES_GLOBAL_FIELD_LEVEL_APPLICATION

  tiles:
    readonly Readonly<
      LogresFieldNavigationTile
    >[]

  tileAt:
    LogresFieldNavigationLookup

  unresolvedPackedChipIds:
    readonly number[]

  duplicateCoordinates:
    readonly string[]

  unaddressedGridCount:
    number

  metadataComplete:
    boolean
}

function safeUint32(
  value:
    bigint | undefined,
  label: string,
): number {
  const safe =
    logresMapSafeInt(
      value ??
        0n,
      label,
    ) ??
    0

  if (
    safe < 0 ||
    safe >
      0xffffffff
  ) {
    throw new Error(
      `${label} must fit native Logres MultiID uint32`,
    )
  }

  return safe
}

function safeLevelScalar(
  value:
    bigint | undefined,
  label: string,
): number {
  return (
    logresMapSafeInt(
      value ??
        0n,
      label,
    ) ??
    0
  )
}

/**
 * Reconstructs the FieldTile movement level contributed by map chip blocks.
 *
 * CONFIRMED ORIGINAL in current native client:
 * - FieldTile constructor initializes level to zero.
 * - FieldQuadTreeStream iterates Grid.Chips in protobuf order.
 * - A resolved chip creates a type-3 FieldBlock.
 * - FieldBlock base level is Chip.Height.
 * - FieldBlock height is InfoChipBin byte at offset 0x18.
 * - The block level is their sum.
 * - FieldTile::updateProperties scans entities backwards and uses the last
 *   type-3 FieldBlock, so the last successfully resolved chip block wins.
 * - A missing map-info lookup is skipped and does not replace the prior level.
 *
 * Applying this formula to recovered May-2017 Global records remains
 * SUPPORTED INFERENCE. The Global map-info tables conform to the same fixed
 * record envelope, but the original Global implementation of this exact
 * function is no longer available on the VM.
 */
export function deriveLogresFieldBlockLevel(
  grid: LogresMapGrid,
  chipInfo: LogresMapInfoTable,
): LogresFieldBlockLevelEvidence {
  if (
    chipInfo.kind !==
    'chip'
  ) {
    throw new Error(
      'Logres field block levels require MAP_CHIP metadata',
    )
  }

  let level = 0
  let resolvedBlockCount = 0

  const unresolved =
    new Set<number>()

  for (
    const chip
    of grid.Chips
  ) {
    const packedId =
      safeUint32(
        chip.Id,
        'Chip.Id',
      )

    const mapInfoHeight =
      logresMapInfoHeight(
        chipInfo,
        packedId,
      )

    if (
      mapInfoHeight ===
      undefined
    ) {
      unresolved.add(
        packedId,
      )

      continue
    }

    const chipHeight =
      safeLevelScalar(
        chip.Height,
        'Chip.Height',
      )

    level =
      chipHeight +
      mapInfoHeight

    if (
      !Number.isSafeInteger(
        level,
      )
    ) {
      throw new Error(
        'Derived Logres field block level exceeds safe integer range',
      )
    }

    resolvedBlockCount +=
      1
  }

  return {
    level,
    resolvedBlockCount,
    unresolvedPackedChipIds:
      Object.freeze(
        [
          ...unresolved,
        ],
      ),
  }
}

function coordKey(
  col: number,
  row: number,
): string {
  return `${col},${row}`
}

/**
 * Builds a pathfinding-ready tile lookup while retaining evidence gaps.
 *
 * No caller should treat metadataComplete=false as an authentic movement
 * surface. The model still exposes derived tiles so diagnostics can show
 * exactly where evidence is missing.
 */
export function createLogresFieldNavigationModel(
  root: LogresMapRoot,
  chipInfo: LogresMapInfoTable,
): LogresFieldNavigationModel {
  if (
    chipInfo.kind !==
    'chip'
  ) {
    throw new Error(
      'Logres navigation model requires MAP_CHIP metadata',
    )
  }

  const gridIndex =
    createLogresFieldGridIndex(
      root,
    )

  const tiles:
    Readonly<
      LogresFieldNavigationTile
    >[] =
      []

  const uniqueTiles =
    new Map<
      string,
      Readonly<
        LogresFieldNavigationTile
      >
    >()

  const duplicateCoordinates:
    string[] =
      []

  const unresolved =
    new Set<number>()

  for (
    const [
      key,
      cells,
    ]
    of gridIndex.cells
  ) {
    if (
      cells.length !==
      1
    ) {
      duplicateCoordinates.push(
        key,
      )
    }

    for (
      const cell
      of cells
    ) {
      const evidence =
        deriveLogresFieldBlockLevel(
          cell.grid,
          chipInfo,
        )

      for (
        const packedId
        of evidence
          .unresolvedPackedChipIds
      ) {
        unresolved.add(
          packedId,
        )
      }

      const tile =
        Object.freeze(
          createLogresFieldNavigationTile(
            cell,
            evidence.level,
          ),
        )

      tiles.push(
        tile,
      )

      if (
        cells.length ===
        1
      ) {
        uniqueTiles.set(
          key,
          tile,
        )
      }
    }
  }

  const unresolvedPackedChipIds =
    Object.freeze(
      [
        ...unresolved,
      ].sort(
        (
          left,
          right,
        ) =>
          left -
          right,
      ),
    )

  const frozenDuplicates =
    Object.freeze(
      [
        ...duplicateCoordinates,
      ].sort(),
    )

  const unaddressedGridCount =
    gridIndex
      .unaddressedGrids
      .length

  return {
    formulaEvidence:
      LOGRES_FIELD_LEVEL_FORMULA_EVIDENCE,

    globalTargetApplication:
      LOGRES_GLOBAL_FIELD_LEVEL_APPLICATION,

    tiles:
      Object.freeze(
        tiles,
      ),

    tileAt:
      (
        col,
        row,
      ) =>
        uniqueTiles.get(
          coordKey(
            col,
            row,
          ),
        ),

    unresolvedPackedChipIds,

    duplicateCoordinates:
      frozenDuplicates,

    unaddressedGridCount,

    metadataComplete:
      unresolvedPackedChipIds
        .length ===
        0 &&
      frozenDuplicates
        .length ===
        0 &&
      unaddressedGridCount ===
        0,
  }
}
