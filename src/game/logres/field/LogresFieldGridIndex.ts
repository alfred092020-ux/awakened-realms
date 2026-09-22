import type {
  LogresMapGrid,
  LogresMapRoot,
} from './LogresMapBinary'
import {
  flattenLogresMapGrids,
  logresMapSafeInt,
} from './LogresMapBinary'

export interface LogresFieldGridNavigationEvidence {
  prohibition?: bigint
  attribute?: bigint
  pathwayIndex?: bigint
  borderId?: bigint
  blendAdjacence?: bigint
  colorIndex?: bigint
}

export interface LogresFieldGridCell {
  col: number
  row: number
  grid: LogresMapGrid
  navigationEvidence: LogresFieldGridNavigationEvidence
}

export interface LogresFieldGridIndex {
  cells: ReadonlyMap<string, readonly LogresFieldGridCell[]>
  unaddressedGrids: readonly LogresMapGrid[]
  at: (col: number, row: number) => readonly LogresFieldGridCell[]
}

function coordKey(col: number, row: number): string {
  if (!Number.isSafeInteger(col) || !Number.isSafeInteger(row)) {
    throw new Error('Logres field coordinates must be safe integers')
  }
  return `${col},${row}`
}

/**
 * CONFIRMED ORIGINAL data only.
 *
 * Builds a lookup over decoded Grid.Col/Grid.Row while preserving raw
 * Prohibition/Attribute/PathwayIndex/BorderID/BlendAdjacence/ColorIndex values.
 * Their gameplay meaning remains UNRESOLVED until native movement/pathfinding
 * evidence establishes the exact semantics.
 *
 * Duplicate coordinates are preserved instead of assuming one grid per coord.
 */
export function createLogresFieldGridIndex(
  root: LogresMapRoot,
): LogresFieldGridIndex {
  const mutable = new Map<string, LogresFieldGridCell[]>()
  const unaddressedGrids: LogresMapGrid[] = []

  for (const grid of flattenLogresMapGrids(root)) {
    const col = logresMapSafeInt(grid.Col, 'Grid.Col')
    const row = logresMapSafeInt(grid.Row, 'Grid.Row')
    if (col === undefined || row === undefined) {
      unaddressedGrids.push(grid)
      continue
    }

    const cell: LogresFieldGridCell = {
      col,
      row,
      grid,
      navigationEvidence: {
        prohibition: grid.Prohibition,
        attribute: grid.Attribute,
        pathwayIndex: grid.PathwayIndex,
        borderId: grid.BorderID,
        blendAdjacence: grid.BlendAdjacence,
        colorIndex: grid.ColorIndex,
      },
    }
    const key = coordKey(col, row)
    const list = mutable.get(key)
    if (list) list.push(cell)
    else mutable.set(key, [cell])
  }

  const cells = new Map<string, readonly LogresFieldGridCell[]>()
  for (const [key, value] of mutable) {
    cells.set(key, Object.freeze([...value]))
  }

  return {
    cells,
    unaddressedGrids: Object.freeze([...unaddressedGrids]),
    at: (col, row) => cells.get(coordKey(col, row)) ?? [],
  }
}
