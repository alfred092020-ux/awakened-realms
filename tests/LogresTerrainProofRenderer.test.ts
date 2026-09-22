import { describe, expect, it } from 'vitest'
import { terrainProofBounds, expandTerrainProofTriangles } from '../src/game/logres/field/LogresTerrainProofRenderer'
import type { LogresTerrainMeshGroup } from '../src/game/logres/field/LogresTerrainMeshData'

const group: LogresTerrainMeshGroup = {
  texture: 'chip', primitiveCount: 1,
  vertices: [-3, 2, 7, 2, 7, 12, -3, 12],
  uvs: [0, 0, 1, 0, 1, 1, 0, 1],
  indices: [0, 3, 1, 1, 3, 2],
}

describe('diagnostic terrain GPU adapter', () => {
  it('expands strip-derived triangles with their matching UVs, without uint16 limits', () => {
    expect([...expandTerrainProofTriangles(group)]).toEqual([
      -3, 2, 0, 0, -3, 12, 0, 1, 7, 2, 1, 0,
      7, 2, 1, 0, -3, 12, 0, 1, 7, 12, 1, 1,
    ])
    const large = { ...group, vertices: new Array(131074).fill(4), uvs: new Array(131074).fill(0.5), indices: [65536, 0, 1] }
    expect(expandTerrainProofTriangles(large).length).toBe(12)
  })
  it('fits original XY across texture groups without assigning gameplay projection', () => {
    expect(terrainProofBounds([group])).toEqual({ centerX: 2, centerY: 7, width: 10, height: 10 })
    expect(() => terrainProofBounds([])).toThrow('No terrain vertices')
  })
  it('rejects malformed geometry before upload', () => {
    expect(() => expandTerrainProofTriangles({ ...group, indices: [0, 1, 99] })).toThrow('index')
    expect(() => expandTerrainProofTriangles({ ...group, uvs: [NaN] })).toThrow()
    expect(() => terrainProofBounds([{ ...group, vertices: [Infinity, 1] }])).toThrow('finite')
  })
})
