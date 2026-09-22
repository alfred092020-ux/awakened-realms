import { describe, expect, it } from 'vitest'
import {
  buildLogresTerrainMeshData,
  LOGRES_RENDERER_PROOF_ATLAS_SIZE,
} from '../src/game/logres/field/LogresTerrainMeshData'
import type { LogresTerrainPrimitiveSet } from '../src/game/logres/field/LogresTerrainPrimitives'

const terrain: LogresTerrainPrimitiveSet = {
  chipCount: 1,
  objectCount: 0,
  animatedObjectCount: 0,
  primitives: [{
    texture: 'chip',
    id: 1n,
    gridCol: 0n,
    gridRow: 0n,
    depthEvidence: { gridDepthOrder: 10n },
    stripOrder: [0, 3, 1, 2],
    vertices: [
      { VertexPos: { PosX: 0, PosY: 0 }, UvPoses: [{ UvX: 0, UvY: 0 }] },
      { VertexPos: { PosX: 10, PosY: 0 }, UvPoses: [{ UvX: 1, UvY: 0 }] },
      { VertexPos: { PosX: 10, PosY: 10 }, UvPoses: [{ UvX: 1, UvY: 1 }] },
      { VertexPos: { PosX: 0, PosY: 10 }, UvPoses: [{ UvX: 0, UvY: 1 }] },
    ],
  }],
}

describe('Logres terrain mesh data', () => {
  it('triangulates the confirmed native strip order and preserves normalized UVs', () => {
    const mesh = buildLogresTerrainMeshData(terrain, { origin: 'top-left' })
    expect(mesh.chip.vertices).toEqual([0,0, 10,0, 10,10, 0,10])
    expect(mesh.chip.uvs).toEqual([0,0, 1,0, 1,1, 0,1])
    expect(mesh.chip.indices).toEqual([0,3,1, 1,3,2])
    expect(mesh.chip.primitiveCount).toBe(1)
    expect(mesh.obj.primitiveCount).toBe(0)
  })

  it('keeps texture-origin uncertainty explicit rather than guessing it', () => {
    const mesh = buildLogresTerrainMeshData(terrain, { origin: 'bottom-left' })
    expect(mesh.chip.uvs.slice(0, 2)).toEqual([0,1])
    expect(mesh.chip.uvs.slice(-2)).toEqual([0,0])
  })

  it('uses the confirmed proof-atlas dimensions', () => {
    expect(LOGRES_RENDERER_PROOF_ATLAS_SIZE).toEqual({
      chip: { width: 718, height: 1938 },
      obj: { width: 2048, height: 1934 },
    })
  })
})

// Recovered current-JP CHIP atlas edge values: 2/718 and 5/1938.
it('does not divide recovered normalized UVs by atlas size a second time', () => {
  const normalized = { UvX: 0.002785515272989869, UvY: 0.0025799793656915426 }
  const source = structuredClone(terrain)
  const first = source.primitives[0]!
  const input = { ...source, primitives: [{ ...first, vertices: [{ ...first.vertices[0]!, UvPoses: [normalized] }, ...first.vertices.slice(1)] }] }
  expect(buildLogresTerrainMeshData(input, { origin: 'top-left' }).chip.uvs.slice(0, 2)).toEqual([normalized.UvX, normalized.UvY])
  expect(buildLogresTerrainMeshData(input, { origin: 'bottom-left' }).chip.uvs.slice(0, 2)).toEqual([normalized.UvX, 1 - normalized.UvY])
})
