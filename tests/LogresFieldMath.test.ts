import { describe, expect, it } from 'vitest'
import {
  LOGRES_PLAYER_DEPTH_ORDER,
  LOGRES_TILE_SIDE_HEIGHT,
  logresCoordToIndex,
} from '../src/game/logres/field/LogresFieldMath'

describe('confirmed native field math', () => {
  it('preserves recovered constants', () => {
    expect(LOGRES_TILE_SIDE_HEIGHT).toBe(22)
    expect(LOGRES_PLAYER_DEPTH_ORDER).toBe(0)
  })

  it('matches native coordToIndex column-major 32-bit MADD semantics', () => {
    expect(logresCoordToIndex({ col: 2, row: 3 }, { cols: 120, rows: 120 })).toBe(243)
    expect(logresCoordToIndex({ col: 0, row: 119 }, { cols: 120, rows: 120 })).toBe(119)
  })

  it('rejects non-native numeric input instead of silently coercing it', () => {
    expect(() => logresCoordToIndex({ col: 1.5, row: 0 }, { cols: 120, rows: 120 }))
      .toThrow(/signed 32-bit/)
  })
})
