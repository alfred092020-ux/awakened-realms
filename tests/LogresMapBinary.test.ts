import { describe, expect, it } from 'vitest'
import {
  decodeLogresMap,
  flattenLogresMapGrids,
  logresMapSafeInt,
} from '../src/game/logres/field/LogresMapBinary'

const concat = (...chunks: Uint8Array[]) => {
  const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0))
  let offset = 0
  for (const chunk of chunks) { out.set(chunk, offset); offset += chunk.length }
  return out
}
const v = (value: bigint) => {
  const bytes: number[] = []
  let x = value
  do {
    let byte = Number(x & 0x7fn)
    x >>= 7n
    if (x) byte |= 0x80
    bytes.push(byte)
  } while (x)
  return Uint8Array.from(bytes)
}
const key = (field: number, wire: number) => v(BigInt((field << 3) | wire))
const scalar = (field: number, value: bigint) => concat(key(field, 0), v(value))
const f32 = (field: number, value: number) => {
  const payload = new Uint8Array(4)
  new DataView(payload.buffer).setFloat32(0, value, true)
  return concat(key(field, 5), payload)
}
const msg = (field: number, payload: Uint8Array) => concat(key(field, 2), v(BigInt(payload.length)), payload)

describe('evidenced Logres map runtime decoder', () => {
  it('decodes the recovered Root/QuadTree/Grid/Chip/Vertex schema losslessly', () => {
    const uv = concat(f32(1, 0.25), f32(2, 0.5))
    const pos = concat(f32(1, 12.5), f32(2, -7.25))
    const vertex = concat(msg(1, pos), msg(2, uv))
    const chip = concat(scalar(1, 99n), scalar(2, 3n), msg(5, vertex))
    const grid = concat(
      scalar(1, 4n), scalar(2, 5n), scalar(3, 11n),
      scalar(4, 1n), scalar(6, 7n), msg(10, chip),
    )
    const bounds = concat(f32(1, -10), f32(2, -20), f32(3, 100), f32(4, 200))
    const tree = concat(msg(1, grid), msg(3, bounds))
    const rootBytes = concat(
      scalar(1, 2n),
      scalar(2, 9861257442030806433n),
      scalar(3, 120n),
      scalar(4, 120n),
      msg(5, tree),
      scalar(6, 8n),
      scalar(7, 8n),
    )

    const root = decodeLogresMap(rootBytes)
    expect(root.UpdateDate).toBe(9861257442030806433n)
    expect(root.Width).toBe(120n)
    expect(root.FieldQuadUnitRow).toBe(8n)
    const [decoded] = flattenLogresMapGrids(root)
    expect(decoded?.Col).toBe(4n)
    expect(decoded?.Prohibition).toBe(1n)
    expect(decoded?.PathwayIndex).toBe(7n)
    expect(decoded?.Chips[0]?.Id).toBe(99n)
    expect(decoded?.Chips[0]?.Vertices[0]?.VertexPos).toEqual({ PosX: 12.5, PosY: -7.25 })
    expect(decoded?.Chips[0]?.Vertices[0]?.UvPoses[0]).toEqual({ UvX: 0.25, UvY: 0.5 })
  })

  it('rejects unknown fields, unsupported wire types and duplicate singular fields', () => {
    expect(() => decodeLogresMap(scalar(99, 1n))).toThrow(/unknown field/)
    expect(() => decodeLogresMap(concat(scalar(3, 1n), scalar(3, 2n)))).toThrow(/Duplicate singular/)
    expect(() => decodeLogresMap(key(1, 1))).toThrow(/Unsupported/)
  })

  it('keeps large original varints lossless until an explicit safe-number conversion', () => {
    const huge = 9861257442030806433n
    const root = decodeLogresMap(scalar(2, huge))
    expect(root.UpdateDate).toBe(huge)
    expect(() => logresMapSafeInt(root.UpdateDate, 'UpdateDate')).toThrow(/safe integer/)
    expect(logresMapSafeInt(120n, 'Width')).toBe(120)
  })
})
