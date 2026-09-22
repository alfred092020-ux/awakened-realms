export interface LogresFieldCoord {
  col: number
  row: number
}

export interface LogresFieldExtent {
  cols: number
  rows: number
}

/** CONFIRMED ORIGINAL: lfs::FieldConstant::tileSideHeight() */
export const LOGRES_TILE_SIDE_HEIGHT = 22

/** CONFIRMED ORIGINAL: lfs::field::FieldPlayer::getDepthOrder() returns zero. */
export const LOGRES_PLAYER_DEPTH_ORDER = 0

function requireInt32(value: number, label: string): number {
  if (!Number.isInteger(value) || value < -0x80000000 || value > 0x7fffffff) {
    throw new Error(`${label} must be a signed 32-bit integer`)
  }
  return value | 0
}

/**
 * CONFIRMED ORIGINAL:
 * native coordToIndex loads Coord.col/row and computes
 *   extent.rows * coord.col + coord.row
 * using a 32-bit MADD. Return mirrors the native W-register zero-extension.
 */
export function logresCoordToIndex(
  coord: LogresFieldCoord,
  extent: LogresFieldExtent,
): number {
  const col = requireInt32(coord.col, 'coord.col')
  const row = requireInt32(coord.row, 'coord.row')
  const rows = requireInt32(extent.rows, 'extent.rows')
  requireInt32(extent.cols, 'extent.cols')
  return (Math.imul(rows, col) + row) >>> 0
}
