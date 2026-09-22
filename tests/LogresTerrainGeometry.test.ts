import { describe, expect, it } from 'vitest'
import { buildTerrainBatches, convexHullStripOrder } from '../src/game/logres/field/LogresTerrainGeometry'

const vertices = (count: number) => Array.from({ length: count }, (_, i) => ({
  VertexPos: { PosX: i, PosY: -i },
  UvPoses: [{ UvX: i / count, UvY: 0.25 }, { UvX: i / count, UvY: 0.5 }],
}))

describe('Global native terrain geometry reconstruction', () => {
  it('reorders convex hulls using alternating back and front indices', () => {
    expect(convexHullStripOrder(4)).toEqual([0, 3, 1, 2])
    expect(convexHullStripOrder(5)).toEqual([0, 4, 1, 3, 2])
    expect(convexHullStripOrder(6)).toEqual([0, 5, 1, 4, 2, 3])
  })
  it('preserves supplied positions, depth, UV poses and native white color', () => {
    const [batch] = buildTerrainBatches([{ vertices: vertices(4), z: -12 }])
    expect(Array.from(batch!.positions)).toEqual([0, -0, -12, 3, -3, -12, 1, -1, -12, 2, -2, -12])
    expect(batch!.uvPoses.map(p => p.length)).toEqual([2, 2, 2, 2])
    expect(Array.from(batch!.initialUvs)).toEqual([0, 0.25, 0.75, 0.25, 0.25, 0.25, 0.5, 0.25])
    expect(Array.from(batch!.colors)).toEqual(Array(16).fill(255))
  })
  it('joins strips with two degenerate vertices', () => {
    const [batch] = buildTerrainBatches([{ vertices: vertices(4), z: 1 }, { vertices: vertices(4), z: 2 }])
    expect(batch!.vertexCount).toBe(10)
    expect(Array.from(batch!.positions.slice(9, 21))).toEqual([2, -2, 1, 2, -2, 1, 0, -0, 2, 0, -0, 2])
  })
  it('starts another batch before reaching 65536 vertices', () => {
    const batches = buildTerrainBatches([{ vertices: vertices(65533), z: 1 }, { vertices: vertices(4), z: 2 }])
    expect(batches.map(b => b.vertexCount)).toEqual([65533, 4])
  })
  it('rejects unrenderable data instead of inventing position or UV defaults', () => {
    expect(() => buildTerrainBatches([{ vertices: [{ VertexPos: { PosX: 1, PosY: 2 }, UvPoses: [] }], z: 0 }])).toThrow()
    expect(() => buildTerrainBatches([{ vertices: vertices(4), z: NaN }])).toThrow()
    expect(buildTerrainBatches([])).toEqual([])
  })
})
