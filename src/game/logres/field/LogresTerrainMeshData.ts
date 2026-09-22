import type {
  LogresTerrainPrimitive,
  LogresTerrainPrimitiveSet,
  LogresTerrainTextureKind,
} from './LogresTerrainPrimitives'

export interface LogresTerrainAtlasSize {
  width: number
  height: number
}

export interface LogresTerrainMeshUvPolicy {
  /** UNRESOLVED until native texture-orientation evidence is complete. */
  origin: 'top-left' | 'bottom-left'
}

export interface LogresTerrainMeshGroup {
  texture: LogresTerrainTextureKind
  vertices: number[]
  uvs: number[]
  indices: number[]
  primitiveCount: number
}

export interface LogresTerrainMeshData {
  chip: LogresTerrainMeshGroup
  obj: LogresTerrainMeshGroup
}

/** CONFIRMED ORIGINAL renderer-proof atlas sizes for map 001_000_00002. */
export const LOGRES_RENDERER_PROOF_ATLAS_SIZE = Object.freeze({
  chip: Object.freeze({ width: 718, height: 1938 }),
  obj: Object.freeze({ width: 2048, height: 1934 }),
})

function requireAtlas(size: LogresTerrainAtlasSize, label: string): void {
  if (
    !Number.isFinite(size.width) ||
    !Number.isFinite(size.height) ||
    size.width <= 0 ||
    size.height <= 0
  ) {
    throw new Error(`${label} atlas dimensions must be positive finite values`)
  }
}

function uv(
  value: number,
  size: number,
  label: string,
): number {
  if (!Number.isFinite(value)) throw new Error(`${label} must be finite`)
  return value / size
}

function emptyGroup(texture: LogresTerrainTextureKind): LogresTerrainMeshGroup {
  return { texture, vertices: [], uvs: [], indices: [], primitiveCount: 0 }
}

function appendPrimitive(
  group: LogresTerrainMeshGroup,
  primitive: LogresTerrainPrimitive,
  atlas: LogresTerrainAtlasSize,
  policy: LogresTerrainMeshUvPolicy,
): void {
  const baseVertex = group.vertices.length / 2
  primitive.vertices.forEach((vertex) => {
    group.vertices.push(vertex.VertexPos.PosX, vertex.VertexPos.PosY)
    const pose = vertex.UvPoses[0]
    if (!pose) throw new Error('Terrain primitive vertex is missing initial UV pose')
    const u = uv(pose.UvX, atlas.width, 'UvX')
    const sourceV = uv(pose.UvY, atlas.height, 'UvY')
    const v = policy.origin === 'top-left' ? sourceV : 1 - sourceV
    group.uvs.push(u, v)
  })

  const order = primitive.stripOrder
  for (let index = 0; index + 2 < order.length; index += 1) {
    const a = baseVertex + order[index]!
    const b = baseVertex + order[index + 1]!
    const c = baseVertex + order[index + 2]!
    // GL triangle strips alternate winding every emitted triangle.
    if ((index & 1) === 0) group.indices.push(a, b, c)
    else group.indices.push(b, a, c)
  }
  group.primitiveCount += 1
}

/**
 * Renderer-ready 2D mesh data from confirmed original map geometry.
 *
 * CONFIRMED ORIGINAL:
 * - vertex positions
 * - first UV pose
 * - convex-hull strip ordering
 * - renderer-proof atlas dimensions
 *
 * UNRESOLVED and therefore caller-supplied:
 * - texture V origin
 *
 * This function intentionally does not assign final Z/depth, camera transforms,
 * tutorial semantics, or UV animation timing.
 */
export function buildLogresTerrainMeshData(
  terrain: LogresTerrainPrimitiveSet,
  policy: LogresTerrainMeshUvPolicy,
  atlas = LOGRES_RENDERER_PROOF_ATLAS_SIZE,
): LogresTerrainMeshData {
  requireAtlas(atlas.chip, 'CHIP')
  requireAtlas(atlas.obj, 'OBJ')

  const result: LogresTerrainMeshData = {
    chip: emptyGroup('chip'),
    obj: emptyGroup('obj'),
  }

  for (const primitive of terrain.primitives) {
    appendPrimitive(
      result[primitive.texture],
      primitive,
      atlas[primitive.texture],
      policy,
    )
  }
  return result
}
