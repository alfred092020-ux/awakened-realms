import { describe, expect, it } from 'vitest'
import type { LogresMapRoot } from '../src/game/logres/field/LogresMapBinary'
import { extractLogresTerrainPrimitives } from '../src/game/logres/field/LogresTerrainPrimitives'

describe('authentic Logres terrain primitive extraction', () => {
  it('preserves chip/object geometry and depth evidence without inventing final z', () => {
    const root: LogresMapRoot = {
      QuadTreeRoot: {
        QuadTrees: [],
        Grids: [{
          Col: 2n,
          Row: 3n,
          DepthOrder: 77n,
          Prohibition: 1n,
          Attribute: 0n,
          PathwayIndex: 4n,
          BorderID: 0n,
          BlendAdjacence: 0n,
          ColorIndex: 0n,
          ObjAnimated: [{ Id: 9n, DepthOrder: 88n }],
          Chips: [{
            Id: 5n,
            Vertices: [
              { VertexPos: { PosX: 1, PosY: 2 }, UvPoses: [{ UvX: 0.1, UvY: 0.2 }] },
              { VertexPos: { PosX: 3, PosY: 4 }, UvPoses: [{ UvX: 0.3, UvY: 0.4 }] },
              { VertexPos: { PosX: 5, PosY: 6 }, UvPoses: [{ UvX: 0.5, UvY: 0.6 }] },
              { VertexPos: { PosX: 7, PosY: 8 }, UvPoses: [{ UvX: 0.7, UvY: 0.8 }] },
            ],
          }],
          Obj: [{
            Id: 6n,
            DepthOrder: 79n,
            Vertices: [
              { VertexPos: { PosX: 10, PosY: 20 }, UvPoses: [{ UvX: 0, UvY: 0 }] },
              { VertexPos: { PosX: 11, PosY: 21 }, UvPoses: [{ UvX: 1, UvY: 0 }] },
              { VertexPos: { PosX: 12, PosY: 22 }, UvPoses: [{ UvX: 1, UvY: 1 }] },
              { VertexPos: { PosX: 13, PosY: 23 }, UvPoses: [{ UvX: 0, UvY: 1 }] },
            ],
          }],
        }],
      },
    }

    const result = extractLogresTerrainPrimitives(root)
    expect(result).toMatchObject({
      chipCount: 1,
      objectCount: 1,
      animatedObjectCount: 1,
    })
    expect(result.primitives[0]).toMatchObject({
      texture: 'chip',
      id: 5n,
      gridCol: 2n,
      gridRow: 3n,
      depthEvidence: { gridDepthOrder: 77n },
      stripOrder: [0, 3, 1, 2],
    })
    expect(result.primitives[1]).toMatchObject({
      texture: 'obj',
      id: 6n,
      depthEvidence: { gridDepthOrder: 77n, objectDepthOrder: 79n },
    })
    expect(result.primitives[0]?.vertices[0]?.VertexPos).toEqual({ PosX: 1, PosY: 2 })
  })

  it('rejects incomplete render vertices instead of guessing', () => {
    const root: LogresMapRoot = {
      QuadTreeRoot: {
        QuadTrees: [],
        Grids: [{
          Chips: [{ Vertices: [{ UvPoses: [{ UvX: 0, UvY: 0 }] }] }],
          Obj: [],
          ObjAnimated: [],
        }],
      },
    }
    expect(() => extractLogresTerrainPrimitives(root)).toThrow(/missing VertexPos/)
  })
})
