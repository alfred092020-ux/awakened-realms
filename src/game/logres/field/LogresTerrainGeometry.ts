/** Global native DataParser::addConvexhullVertices, evidence at 0x192f690.
 * Builds geometry only. The caller supplies evidenced draw order and depth.
 * Does not choose a map, camera transform, texture color space or animation speed.
 */
export interface MapUv { UvX: number; UvY: number }
export interface MapVertex {
  VertexPos: { PosX: number; PosY: number }
  UvPoses: readonly MapUv[]
}
export interface TerrainHull { vertices: readonly MapVertex[]; z: number }
export interface TerrainBatch {
  vertexCount: number
  positions: Float32Array
  colors: Uint8Array
  initialUvs: Float32Array
  /** Every pose is retained for the separately reconstructed animator. */
  uvPoses: readonly (readonly MapUv[])[]
}

export const TERRAIN_DRAW_STATE = Object.freeze({
  primitive: 5, // GL_TRIANGLE_STRIP
  sourceBlend: 1, // GL_ONE
  destinationBlend: 0x303, // GL_ONE_MINUS_SRC_ALPHA
  magnificationFilter: 0x2600, // GL_NEAREST
  maxBatchVertices: 65535,
})

export function convexHullStripOrder(count: number): number[] {
  if (!Number.isSafeInteger(count) || count < 0 || count > 65535) {
    throw new Error('Unsupported terrain hull vertex count')
  }
  const order: number[] = []
  let front = 0
  let back = count - 1
  while (front <= back) {
    order.push(front++)
    if (front <= back) order.push(back--)
  }
  return order
}

interface PreparedVertex { x: number; y: number; z: number; poses: readonly MapUv[] }

export function buildTerrainBatches(hulls: readonly TerrainHull[]): TerrainBatch[] {
  const result: TerrainBatch[] = []
  let pending: PreparedVertex[] = []
  const flush = () => {
    if (!pending.length) return
    const positions = new Float32Array(pending.length * 3)
    const initialUvs = new Float32Array(pending.length * 2)
    pending.forEach((v, i) => {
      positions.set([v.x, v.y, v.z], i * 3)
      initialUvs.set([v.poses[0]!.UvX, v.poses[0]!.UvY], i * 2)
    })
    result.push({
      vertexCount: pending.length, positions, initialUvs,
      colors: new Uint8Array(pending.length * 4).fill(255),
      uvPoses: pending.map(v => v.poses),
    })
    pending = []
  }
  for (const hull of hulls) {
    if (!Number.isFinite(hull.z) || !Number.isFinite(Math.fround(hull.z))) {
      throw new Error('Terrain depth must be finite float32')
    }
    if (!hull.vertices.length) continue
    const ordered = convexHullStripOrder(hull.vertices.length).map(index => {
      const vertex = hull.vertices[index]!
      const { PosX: x, PosY: y } = vertex.VertexPos
      if (![x, y].every(v => Number.isFinite(v) && Number.isFinite(Math.fround(v))) || !vertex.UvPoses.length) {
        throw new Error('Terrain vertex requires finite position and UV poses')
      }
      const poses = vertex.UvPoses.map(({ UvX, UvY }) => {
        if (![UvX, UvY].every(v => Number.isFinite(v) && Number.isFinite(Math.fround(v)))) {
          throw new Error('Terrain UV must be finite float32')
        }
        return { UvX, UvY }
      })
      return { x, y, z: hull.z, poses }
    })
    // Native code starts a batch when (old + incoming + 2) >> 16 is nonzero.
    if (pending.length && pending.length + ordered.length + 2 >= 65536) flush()
    if (pending.length) pending.push(pending[pending.length - 1]!, ordered[0]!)
    // Avoid argument-spread limits for large batches.
    for (const vertex of ordered) pending.push(vertex)
  }
  flush()
  return result
}
