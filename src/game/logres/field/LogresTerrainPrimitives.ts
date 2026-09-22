import type {
  LogresMapGrid,
  LogresMapRoot,
  LogresMapVertex,
} from './LogresMapBinary'
import { flattenLogresMapGrids } from './LogresMapBinary'
import {
  convexHullStripOrder,
  type MapVertex,
} from './LogresTerrainGeometry'

export type LogresTerrainTextureKind = 'chip' | 'obj'

export interface LogresTerrainPrimitiveDepthEvidence {
  gridDepthOrder?: bigint
  objectDepthOrder?: bigint
}

export interface LogresTerrainPrimitive {
  texture: LogresTerrainTextureKind
  id?: bigint
  gridCol?: bigint
  gridRow?: bigint
  depthEvidence: LogresTerrainPrimitiveDepthEvidence
  vertices: readonly MapVertex[]
  stripOrder: readonly number[]
}

export interface LogresTerrainPrimitiveSet {
  primitives: readonly LogresTerrainPrimitive[]
  animatedObjectCount: number
  chipCount: number
  objectCount: number
}

/**
 * CONFIRMED ORIGINAL structure only.
 *
 * This converts decoded map entities into renderer-ready convex hull primitives
 * while intentionally preserving depth as evidence metadata. It does NOT choose
 * the final Z transform, projection, camera, texture orientation, or tutorial map.
 */
export function extractLogresTerrainPrimitives(
  root: LogresMapRoot,
): LogresTerrainPrimitiveSet {
  const primitives: LogresTerrainPrimitive[] = []
  let animatedObjectCount = 0
  let chipCount = 0
  let objectCount = 0

  for (const grid of flattenLogresMapGrids(root)) {
    chipCount += grid.Chips.length
    objectCount += grid.Obj.length
    animatedObjectCount += grid.ObjAnimated.length

    for (const chip of grid.Chips) {
      primitives.push({
        texture: 'chip',
        id: chip.Id,
        gridCol: grid.Col,
        gridRow: grid.Row,
        depthEvidence: {
          gridDepthOrder: grid.DepthOrder,
        },
        vertices: requireRenderableVertices(chip.Vertices, 'chip', grid),
        stripOrder: convexHullStripOrder(chip.Vertices.length),
      })
    }

    for (const object of grid.Obj) {
      primitives.push({
        texture: 'obj',
        id: object.Id,
        gridCol: grid.Col,
        gridRow: grid.Row,
        depthEvidence: {
          gridDepthOrder: grid.DepthOrder,
          objectDepthOrder: object.DepthOrder,
        },
        vertices: requireRenderableVertices(object.Vertices, 'object', grid),
        stripOrder: convexHullStripOrder(object.Vertices.length),
      })
    }
  }

  return {
    primitives,
    animatedObjectCount,
    chipCount,
    objectCount,
  }
}

function requireRenderableVertices(
  vertices: readonly LogresMapVertex[],
  source: 'chip' | 'object',
  grid: LogresMapGrid,
): MapVertex[] {
  return vertices.map((vertex, index) => {
    if (!vertex.VertexPos) {
      throw new Error(
        `${source} vertex ${index} is missing VertexPos at grid ${String(grid.Col)},${String(grid.Row)}`,
      )
    }
    if (!vertex.UvPoses.length) {
      throw new Error(
        `${source} vertex ${index} has no UV poses at grid ${String(grid.Col)},${String(grid.Row)}`,
      )
    }
    return {
      VertexPos: {
        PosX: vertex.VertexPos.PosX,
        PosY: vertex.VertexPos.PosY,
      },
      UvPoses: vertex.UvPoses.map(({ UvX, UvY }) => ({ UvX, UvY })),
    }
  })
}
