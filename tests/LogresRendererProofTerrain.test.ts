import { describe, expect, it } from 'vitest'
import type { LoadedLogresRendererProofMap } from '../src/game/logres/field/LogresRendererProofMap'
import { composeLogresRendererProofTerrain } from '../src/game/logres/field/LogresRendererProofTerrain'
import { logresRendererProofAssetUrls } from '../src/game/logres/field/LogresRendererProofAssets'

describe('renderer-proof terrain runtime composition', () => {
  it('joins decoded authentic map geometry to private CHIP/OBJ texture URLs without depth guesses', () => {
    const map: LoadedLogresRendererProofMap = {
      mapId: '001_000_00002',
      role: 'RENDERER_PROOF_NOT_TUTORIAL_MAP',
      width: 120,
      height: 120,
      fieldQuadUnitRow: 8,
      fieldQuadUnitCol: 8,
      gridCount: 1,
      root: {
        QuadTreeRoot: {
          QuadTrees: [],
          Grids: [{
            Col: 1n,
            Row: 2n,
            DepthOrder: 99n,
            Chips: [{
              Id: 7n,
              Vertices: [
                { VertexPos: { PosX: 0, PosY: 0 }, UvPoses: [{ UvX: 0, UvY: 0 }] },
                { VertexPos: { PosX: 1, PosY: 0 }, UvPoses: [{ UvX: 1, UvY: 0 }] },
                { VertexPos: { PosX: 1, PosY: 1 }, UvPoses: [{ UvX: 1, UvY: 1 }] },
              ],
            }],
            Obj: [],
            ObjAnimated: [],
          }],
        },
      },
    }
    const urls = logresRendererProofAssetUrls('/proof')
    const result = composeLogresRendererProofTerrain(map, urls)
    expect(result.textures).toEqual({
      chipPng: '/proof/001_000_00002_CHIP.png',
      objPng: '/proof/001_000_00002_OBJ.png',
    })
    expect(result.terrain.chipCount).toBe(1)
    expect(result.terrain.primitives[0]?.depthEvidence.gridDepthOrder).toBe(99n)
    expect(result.terrain.primitives[0]?.stripOrder).toEqual([0, 2, 1])
  })
})
