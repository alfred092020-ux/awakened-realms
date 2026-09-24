import type {
  LogresFieldCoord,
  LogresFieldNavigationLookup,
  LogresFieldNavigationTile,
} from './LogresFieldNavigation'

export const LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE =
  'CONFIRMED_GLOBAL_3_0_24_NATIVE' as const

export interface LogresGlobalMoveTargetResolution {
  provenance:
    typeof LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE

  requested:
    Readonly<LogresFieldCoord>

  resolved:
    Readonly<LogresFieldNavigationTile>

  usedFallback:
    boolean
}

function freezeCoord(
  coord:
    LogresFieldCoord,
): Readonly<LogresFieldCoord> {
  return Object.freeze({
    col:
      coord.col,

    row:
      coord.row,
  })
}

function sign(
  value:
    number,
): number {
  return value < 0
    ? -1
    : 1
}

/**
 * CONFIRMED GLOBAL 3.0.24.
 *
 * MovePathInitializer::findPossibleMoveLocation builds a candidate vector
 * beginning at the requested target, then walks the integer line back toward
 * the source coordinate using a doubled-error Bresenham accumulator.
 */
export function logresGlobalMoveFallbackCandidates(
  source:
    LogresFieldCoord,
  requested:
    LogresFieldCoord,
): readonly Readonly<LogresFieldCoord>[] {
  if (
    !Number.isSafeInteger(
      source.col,
    ) ||
    !Number.isSafeInteger(
      source.row,
    ) ||
    !Number.isSafeInteger(
      requested.col,
    ) ||
    !Number.isSafeInteger(
      requested.row,
    )
  ) {
    throw new Error(
      'Global move fallback coordinates must be safe integers',
    )
  }

  const result:
    Readonly<LogresFieldCoord>[] =
    [
      freezeCoord(
        requested,
      ),
    ]

  const deltaCol =
    source.col -
    requested.col

  const deltaRow =
    source.row -
    requested.row

  const absCol =
    Math.abs(
      deltaCol,
    )

  const absRow =
    Math.abs(
      deltaRow,
    )

  if (
    absCol === 0 &&
    absRow === 0
  ) {
    return Object.freeze(
      result,
    )
  }

  const colStep =
    sign(
      deltaCol,
    )

  const rowStep =
    sign(
      deltaRow,
    )

  let col =
    requested.col

  let row =
    requested.row

  if (
    absCol >
    absRow
  ) {
    let error =
      absCol

    const doubledMajor =
      absCol *
      2

    const doubledMinor =
      absRow *
      2

    for (
      let index =
        0;
      index <
        absCol;
      index +=
        1
    ) {
      col +=
        colStep

      error +=
        doubledMinor

      if (
        error >
        doubledMajor
      ) {
        error -=
          doubledMajor

        row +=
          rowStep
      }

      result.push(
        freezeCoord({
          col,
          row,
        }),
      )
    }
  } else {
    let error =
      absRow

    const doubledMajor =
      absRow *
      2

    const doubledMinor =
      absCol *
      2

    for (
      let index =
        0;
      index <
        absRow;
      index +=
        1
    ) {
      row +=
        rowStep

      error +=
        doubledMinor

      if (
        error >
        doubledMajor
      ) {
        error -=
          doubledMajor

        col +=
          colStep
      }

      result.push(
        freezeCoord({
          col,
          row,
        }),
      )
    }
  }

  return Object.freeze(
    result,
  )
}

/**
 * CONFIRMED GLOBAL 3.0.24 target-resolution semantics from
 * MovePathInitializer::moveTo/findPossibleMoveLocation.
 *
 * Native A* still runs after this target resolution. This helper does not
 * replace the already-evidenced FieldTile link/level/corner rules.
 */
export function resolveLogresGlobalMoveTarget(
  source:
    LogresFieldNavigationTile,
  requested:
    LogresFieldNavigationTile,
  tileAt:
    LogresFieldNavigationLookup,
): Readonly<LogresGlobalMoveTargetResolution> | null {
  const sourceTile =
    tileAt(
      source.col,
      source.row,
    )

  const requestedTile =
    tileAt(
      requested.col,
      requested.row,
    )

  if (
    !sourceTile ||
    !requestedTile ||
    sourceTile.prohibited
  ) {
    return null
  }

  if (
    !requestedTile.prohibited &&
    requestedTile.regionId ===
      sourceTile.regionId
  ) {
    return Object.freeze({
      provenance:
        LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,

      requested:
        freezeCoord(
          requestedTile,
        ),

      resolved:
        requestedTile,

      usedFallback:
        false,
    })
  }

  for (
    const candidate
    of logresGlobalMoveFallbackCandidates(
      sourceTile,
      requestedTile,
    )
  ) {
    const tile =
      tileAt(
        candidate.col,
        candidate.row,
      )

    if (
      !tile ||
      tile.prohibited ||
      tile.regionId !==
        sourceTile.regionId
    ) {
      continue
    }

    return Object.freeze({
      provenance:
        LOGRES_GLOBAL_3024_NATIVE_FIELD_PROVENANCE,

      requested:
        freezeCoord(
          requestedTile,
        ),

      resolved:
        tile,

      usedFallback:
        true,
    })
  }

  return null
}
