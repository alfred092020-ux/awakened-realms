import type {
  LogresFieldGridCell,
} from './LogresFieldGridIndex'
import type {
  LogresMapGrid,
} from './LogresMapBinary'
import {
  logresMapSafeInt,
} from './LogresMapBinary'

export interface LogresFieldCoord {
  col: number
  row: number
}

export interface LogresFieldNavigationTile
  extends LogresFieldCoord {
  prohibited: boolean
  level: number
  regionId: number
  attribute: number
}

export type LogresFieldNavigationLookup =
  (
    col: number,
    row: number,
  ) =>
    | LogresFieldNavigationTile
    | undefined

/**
 * CONFIRMED ORIGINAL native TileAdjacency enum order.
 *
 * Recovered directly from TerrainAccessor::s_adjacencies static initialization:
 * 0 NW, 1 N, 2 NE, 3 E, 4 SE, 5 S, 6 SW, 7 W, 8 center.
 *
 * FieldTile::applyStructureHeightToTiles specifically walks index 7 across
 * structure columns and index 1 across structure rows.
 */
export const LOGRES_FIELD_ADJACENCY_DELTAS =
  Object.freeze([
    Object.freeze({ col: -1, row: -1 }),
    Object.freeze({ col: 0, row: -1 }),
    Object.freeze({ col: 1, row: -1 }),
    Object.freeze({ col: 1, row: 0 }),
    Object.freeze({ col: 1, row: 1 }),
    Object.freeze({ col: 0, row: 1 }),
    Object.freeze({ col: -1, row: 1 }),
    Object.freeze({ col: -1, row: 0 }),
    Object.freeze({ col: 0, row: 0 }),
  ] as const)

/**
 * CONFIRMED ORIGINAL neighbor coordinate set.
 *
 * The current native client accepts only coordinate deltas whose absolute
 * components are <= 1 and rejects the center (0, 0), yielding exactly the
 * eight surrounding coordinates.
 *
 * Array order is intentionally non-semantic. Native adjacency enum ordering is
 * not required for coordinate-based reconstruction and is not asserted here.
 */
export const LOGRES_FIELD_NEIGHBOR_DELTAS =
  Object.freeze([
    Object.freeze({
      col: -1,
      row: -1,
    }),
    Object.freeze({
      col: 0,
      row: -1,
    }),
    Object.freeze({
      col: 1,
      row: -1,
    }),
    Object.freeze({
      col: -1,
      row: 0,
    }),
    Object.freeze({
      col: 1,
      row: 0,
    }),
    Object.freeze({
      col: -1,
      row: 1,
    }),
    Object.freeze({
      col: 0,
      row: 1,
    }),
    Object.freeze({
      col: 1,
      row: 1,
    }),
  ] as const)

function requireSafeInteger(
  value: number,
  label: string,
): number {
  if (!Number.isSafeInteger(value)) {
    throw new Error(
      `${label} must be a safe integer`,
    )
  }

  return value
}

function gridScalar(
  value: bigint | undefined,
  label: string,
): number {
  return (
    logresMapSafeInt(
      value ?? 0n,
      label,
    ) ??
    0
  )
}

/**
 * CONFIRMED ORIGINAL protobuf/native semantics:
 * absent scalar fields default to zero, and Grid.Prohibition is converted to a
 * boolean by testing whether the decoded value is non-zero before FieldTile
 * setup.
 */
export function logresGridIsProhibited(
  grid: LogresMapGrid,
): boolean {
  return (
    grid.Prohibition ??
    0n
  ) !== 0n
}

/**
 * CONFIRMED ORIGINAL: Grid.PathwayIndex is passed into FieldTile::setupParam
 * and returned by native FieldTile::getRegionID().
 */
export function logresGridRegionId(
  grid: LogresMapGrid,
): number {
  return gridScalar(
    grid.PathwayIndex,
    'Grid.PathwayIndex',
  )
}

/**
 * CONFIRMED ORIGINAL: Grid.Attribute is passed into FieldTile::setupParam and
 * returned unchanged by native FieldTile::getAttribute().
 */
export function logresGridAttribute(
  grid: LogresMapGrid,
): number {
  return gridScalar(
    grid.Attribute,
    'Grid.Attribute',
  )
}

/**
 * Creates the navigation portion of one tile from decoded map evidence.
 *
 * Level is deliberately supplied by the caller. Native FieldTile movement
 * level is structure/block-derived state and MUST NOT be substituted with raw
 * Grid.DepthOrder.
 */
export function createLogresFieldNavigationTile(
  cell: LogresFieldGridCell,
  level: number,
): LogresFieldNavigationTile {
  return {
    col:
      requireSafeInteger(
        cell.col,
        'Field tile col',
      ),
    row:
      requireSafeInteger(
        cell.row,
        'Field tile row',
      ),
    prohibited:
      logresGridIsProhibited(
        cell.grid,
      ),
    level:
      requireSafeInteger(
        level,
        'Field tile level',
      ),
    regionId:
      logresGridRegionId(
        cell.grid,
      ),
    attribute:
      logresGridAttribute(
        cell.grid,
      ),
  }
}

export function isLogresFieldNeighborDelta(
  colDelta: number,
  rowDelta: number,
): boolean {
  if (
    !Number.isSafeInteger(
      colDelta,
    ) ||
    !Number.isSafeInteger(
      rowDelta,
    )
  ) {
    return false
  }

  return (
    Math.abs(
      colDelta,
    ) <= 1 &&
    Math.abs(
      rowDelta,
    ) <= 1 &&
    (
      colDelta !== 0 ||
      rowDelta !== 0
    )
  )
}

/**
 * CONFIRMED ORIGINAL link cost.
 *
 * Native FieldTile::calculateLinkNodeCost returns Manhattan coordinate
 * distance, making cardinal links cost 1 and diagonal links cost 2.
 */
export function logresFieldLinkCost(
  from: LogresFieldCoord,
  to: LogresFieldCoord,
): number {
  return (
    Math.abs(
      to.col -
        from.col,
    ) +
    Math.abs(
      to.row -
        from.row,
    )
  )
}

/**
 * CONFIRMED ORIGINAL FieldTile heuristic.
 *
 * Native FieldTile::calculateHeuristic returns zero, so the tile graph behaves
 * like Dijkstra search unless a different node-info implementation is used.
 */
export function logresFieldHeuristic():
  number {
  return 0
}

function traversableRelativeTo(
  origin: LogresFieldNavigationTile,
  candidate:
    | LogresFieldNavigationTile
    | undefined,
): candidate is LogresFieldNavigationTile {
  if (
    !candidate ||
    candidate.prohibited
  ) {
    return false
  }

  return (
    Math.abs(
      candidate.level -
        origin.level,
    ) <= 1
  )
}

/**
 * CONFIRMED ORIGINAL FieldTile::getLinkNode semantics expressed by coordinates.
 *
 * Destination requirements:
 * - one of the eight neighboring coordinates
 * - tile exists
 * - Prohibition == 0
 * - absolute movement-level difference <= 1
 *
 * Diagonal movement additionally requires both adjacent orthogonal tiles to
 * satisfy the same blocked/level checks. This reproduces the native corner-cut
 * prevention without depending on the private adjacency enum ordering.
 */
export function logresFieldCanTraverseNeighbor(
  from: LogresFieldNavigationTile,
  colDelta: number,
  rowDelta: number,
  tileAt: LogresFieldNavigationLookup,
): boolean {
  if (
    !isLogresFieldNeighborDelta(
      colDelta,
      rowDelta,
    )
  ) {
    return false
  }

  const target =
    tileAt(
      from.col +
        colDelta,
      from.row +
        rowDelta,
    )

  if (
    !traversableRelativeTo(
      from,
      target,
    )
  ) {
    return false
  }

  const diagonal =
    colDelta !== 0 &&
    rowDelta !== 0

  if (!diagonal) {
    return true
  }

  const colSide =
    tileAt(
      from.col +
        colDelta,
      from.row,
    )

  const rowSide =
    tileAt(
      from.col,
      from.row +
        rowDelta,
    )

  return (
    traversableRelativeTo(
      from,
      colSide,
    ) &&
    traversableRelativeTo(
      from,
      rowSide,
    )
  )
}

export function logresFieldLinkedNeighbors(
  from: LogresFieldNavigationTile,
  tileAt: LogresFieldNavigationLookup,
): readonly LogresFieldNavigationTile[] {
  const result:
    LogresFieldNavigationTile[] =
    []

  for (
    const delta
    of LOGRES_FIELD_NEIGHBOR_DELTAS
  ) {
    if (
      !logresFieldCanTraverseNeighbor(
        from,
        delta.col,
        delta.row,
        tileAt,
      )
    ) {
      continue
    }

    const target =
      tileAt(
        from.col +
          delta.col,
        from.row +
          delta.row,
      )

    if (target) {
      result.push(
        target,
      )
    }
  }

  return Object.freeze(
    result,
  )
}
