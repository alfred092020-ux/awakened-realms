/**
 * Runtime decoder for the evidenced original Logres .map protobuf payload.
 *
 * CONFIRMED ORIGINAL:
 * - field numbers/names from the recovered Global client schema
 * - wire types/cardinalities validated against recovered Japanese maps
 *
 * UNRESOLVED:
 * - world-space projection, final Z/depth conversion, texture color space,
 *   UV animation timing, collision value semantics and tutorial-map selection.
 *
 * Input must be the decompressed .map protobuf payload, not the outer MBN or gzip.
 */
export interface LogresMapUv { UvX: number; UvY: number }
export interface LogresMapVertexPos { PosX: number; PosY: number }
export interface LogresMapVertex {
  VertexPos?: LogresMapVertexPos
  UvPoses: LogresMapUv[]
}
export interface LogresMapChip {
  Id?: bigint
  Height?: bigint
  ShadowID?: bigint
  ShadowAlpha?: number
  Vertices: LogresMapVertex[]
}
export interface LogresMapObject {
  Id?: bigint
  DepthOrder?: bigint
  Vertices: LogresMapVertex[]
}
export interface LogresMapObjectAnimated {
  Id?: bigint
  DepthOrder?: bigint
}
export interface LogresMapGrid {
  Col?: bigint
  Row?: bigint
  DepthOrder?: bigint
  Prohibition?: bigint
  Attribute?: bigint
  PathwayIndex?: bigint
  BorderID?: bigint
  BlendAdjacence?: bigint
  ColorIndex?: bigint
  Chips: LogresMapChip[]
  Obj: LogresMapObject[]
  ObjAnimated: LogresMapObjectAnimated[]
}
export interface LogresMapBoundingBox {
  OriginX?: number
  OriginY?: number
  SizeX?: number
  SizeY?: number
}
export interface LogresMapQuadTree {
  Grids: LogresMapGrid[]
  QuadTrees: LogresMapQuadTree[]
  BoundingBox?: LogresMapBoundingBox
}
export interface LogresMapRoot {
  Version?: bigint
  UpdateDate?: bigint
  Width?: bigint
  Height?: bigint
  QuadTreeRoot?: LogresMapQuadTree
  FieldQuadUnitRow?: bigint
  FieldQuadUnitCol?: bigint
}

interface WireField {
  number: number
  wireType: number
  varint?: bigint
  bytes?: Uint8Array
  fixed32?: number
}

class Cursor {
  offset = 0; data: Uint8Array
  constructor(data: Uint8Array) { this.data = data }

  remaining() {
    return this.data.length - this.offset
  }

  readByte(): number {
    if (this.offset >= this.data.length) throw new Error('Unexpected end of Logres map payload')
    return this.data[this.offset++]!
  }

  readVarint(): bigint {
    let value = 0n
    let shift = 0n
    for (let index = 0; index < 10; index += 1) {
      const byte = this.readByte()
      value |= BigInt(byte & 0x7f) << shift
      if ((byte & 0x80) === 0) return value
      shift += 7n
    }
    throw new Error('Varint exceeds 10 bytes')
  }

  readBytes(length: number): Uint8Array {
    if (!Number.isSafeInteger(length) || length < 0 || length > this.remaining()) {
      throw new Error('Invalid length-delimited Logres map field')
    }
    const start = this.offset
    this.offset += length
    return this.data.subarray(start, this.offset)
  }

  readFloat32(): number {
    if (this.remaining() < 4) throw new Error('Truncated fixed32 Logres map field')
    const view = new DataView(this.data.buffer, this.data.byteOffset + this.offset, 4)
    const value = view.getFloat32(0, true)
    this.offset += 4
    if (!Number.isFinite(value)) throw new Error('Non-finite Logres map geometry value')
    return value
  }
}

function toSafeLength(value: bigint): number {
  if (value < 0n || value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error('Length-delimited field exceeds JavaScript safe range')
  }
  return Number(value)
}

function readFields(data: Uint8Array): WireField[] {
  const cursor = new Cursor(data)
  const result: WireField[] = []
  while (cursor.remaining() > 0) {
    const key = cursor.readVarint()
    const fieldNumber = Number(key >> 3n)
    const wireType = Number(key & 0x7n)
    if (!Number.isSafeInteger(fieldNumber) || fieldNumber <= 0) {
      throw new Error('Invalid Logres map field number')
    }
    if (wireType === 0) {
      result.push({ number: fieldNumber, wireType, varint: cursor.readVarint() })
    } else if (wireType === 2) {
      const length = toSafeLength(cursor.readVarint())
      result.push({ number: fieldNumber, wireType, bytes: cursor.readBytes(length) })
    } else if (wireType === 5) {
      result.push({ number: fieldNumber, wireType, fixed32: cursor.readFloat32() })
    } else {
      throw new Error(`Unsupported Logres map wire type ${wireType}`)
    }
  }
  return result
}

function singular<T>(target: Record<string, unknown>, key: string, value: T): T {
  if (Object.prototype.hasOwnProperty.call(target, key)) {
    throw new Error(`Duplicate singular Logres map field: ${key}`)
  }
  ;(target as Record<string, T>)[key] = value
  return value
}

function expectWire(field: WireField, wireType: number, label: string) {
  if (field.wireType !== wireType) {
    throw new Error(`${label}: unexpected wire type ${field.wireType}`)
  }
}

function bytes(field: WireField, label: string): Uint8Array {
  expectWire(field, 2, label)
  if (!field.bytes) throw new Error(`${label}: missing bytes`)
  return field.bytes
}

function varint(field: WireField, label: string): bigint {
  expectWire(field, 0, label)
  if (field.varint === undefined) throw new Error(`${label}: missing varint`)
  return field.varint
}

function fixed32(field: WireField, label: string): number {
  expectWire(field, 5, label)
  if (field.fixed32 === undefined) throw new Error(`${label}: missing fixed32`)
  return field.fixed32
}

function decodeUv(data: Uint8Array): LogresMapUv {
  const out: Partial<LogresMapUv> = {}
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as Record<string, unknown>, 'UvX', fixed32(field, 'UVPos.UvX'))
    else if (field.number === 2) singular(out as Record<string, unknown>, 'UvY', fixed32(field, 'UVPos.UvY'))
    else throw new Error(`UVPos: unknown field ${field.number}:${field.wireType}`)
  }
  if (out.UvX === undefined || out.UvY === undefined) throw new Error('UVPos requires UvX and UvY')
  return out as LogresMapUv
}

function decodeVertexPos(data: Uint8Array): LogresMapVertexPos {
  const out: Partial<LogresMapVertexPos> = {}
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as Record<string, unknown>, 'PosX', fixed32(field, 'VertexPos.PosX'))
    else if (field.number === 2) singular(out as Record<string, unknown>, 'PosY', fixed32(field, 'VertexPos.PosY'))
    else throw new Error(`VertexPos: unknown field ${field.number}:${field.wireType}`)
  }
  if (out.PosX === undefined || out.PosY === undefined) throw new Error('VertexPos requires PosX and PosY')
  return out as LogresMapVertexPos
}

function decodeVertex(data: Uint8Array): LogresMapVertex {
  const out: LogresMapVertex = { UvPoses: [] }
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as unknown as Record<string, unknown>, 'VertexPos', decodeVertexPos(bytes(field, 'Vertex.VertexPos')))
    else if (field.number === 2) out.UvPoses.push(decodeUv(bytes(field, 'Vertex.UvPoses')))
    else throw new Error(`Vertex: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

function decodeChip(data: Uint8Array): LogresMapChip {
  const out: LogresMapChip = { Vertices: [] }
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as unknown as Record<string, unknown>, 'Id', varint(field, 'Chip.Id'))
    else if (field.number === 2) singular(out as unknown as Record<string, unknown>, 'Height', varint(field, 'Chip.Height'))
    else if (field.number === 3) singular(out as unknown as Record<string, unknown>, 'ShadowID', varint(field, 'Chip.ShadowID'))
    else if (field.number === 4) singular(out as unknown as Record<string, unknown>, 'ShadowAlpha', fixed32(field, 'Chip.ShadowAlpha'))
    else if (field.number === 5) out.Vertices.push(decodeVertex(bytes(field, 'Chip.Vertices')))
    else throw new Error(`Chip: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

function decodeObject(data: Uint8Array): LogresMapObject {
  const out: LogresMapObject = { Vertices: [] }
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as unknown as Record<string, unknown>, 'Id', varint(field, 'Object.Id'))
    else if (field.number === 2) singular(out as unknown as Record<string, unknown>, 'DepthOrder', varint(field, 'Object.DepthOrder'))
    else if (field.number === 3) out.Vertices.push(decodeVertex(bytes(field, 'Object.Vertices')))
    else throw new Error(`Object: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

function decodeObjectAnimated(data: Uint8Array): LogresMapObjectAnimated {
  const out: LogresMapObjectAnimated = {}
  for (const field of readFields(data)) {
    if (field.number === 1) singular(out as Record<string, unknown>, 'Id', varint(field, 'ObjectAnimated.Id'))
    else if (field.number === 2) singular(out as Record<string, unknown>, 'DepthOrder', varint(field, 'ObjectAnimated.DepthOrder'))
    else throw new Error(`ObjectAnimated: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

function decodeGrid(data: Uint8Array): LogresMapGrid {
  const out: LogresMapGrid = { Chips: [], Obj: [], ObjAnimated: [] }
  for (const field of readFields(data)) {
    const singles: Record<number, keyof LogresMapGrid> = {
      1: 'Col', 2: 'Row', 3: 'DepthOrder', 4: 'Prohibition', 5: 'Attribute',
      6: 'PathwayIndex', 7: 'BorderID', 8: 'BlendAdjacence', 9: 'ColorIndex',
    }
    const key = singles[field.number]
    if (key) singular(out as unknown as Record<string, unknown>, key, varint(field, `Grid.${key}`))
    else if (field.number === 10) out.Chips.push(decodeChip(bytes(field, 'Grid.Chips')))
    else if (field.number === 11) out.Obj.push(decodeObject(bytes(field, 'Grid.Obj')))
    else if (field.number === 12) out.ObjAnimated.push(decodeObjectAnimated(bytes(field, 'Grid.ObjAnimated')))
    else throw new Error(`Grid: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

function decodeBoundingBox(data: Uint8Array): LogresMapBoundingBox {
  const out: LogresMapBoundingBox = {}
  const names: Record<number, keyof LogresMapBoundingBox> = {
    1: 'OriginX', 2: 'OriginY', 3: 'SizeX', 4: 'SizeY',
  }
  for (const field of readFields(data)) {
    const key = names[field.number]
    if (!key) throw new Error(`BoundingBox: unknown field ${field.number}:${field.wireType}`)
    singular(out as Record<string, unknown>, key, fixed32(field, `BoundingBox.${key}`))
  }
  return out
}

function decodeQuadTree(data: Uint8Array, depth = 0): LogresMapQuadTree {
  if (depth > 64) throw new Error('Logres map quadtree exceeds 64 levels')
  const out: LogresMapQuadTree = { Grids: [], QuadTrees: [] }
  for (const field of readFields(data)) {
    if (field.number === 1) out.Grids.push(decodeGrid(bytes(field, 'QuadTree.Grids')))
    else if (field.number === 2) out.QuadTrees.push(decodeQuadTree(bytes(field, 'QuadTree.QuadTrees'), depth + 1))
    else if (field.number === 3) singular(out as unknown as Record<string, unknown>, 'BoundingBox', decodeBoundingBox(bytes(field, 'QuadTree.BoundingBox')))
    else throw new Error(`QuadTree: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

export function decodeLogresMap(data: Uint8Array): LogresMapRoot {
  const out: LogresMapRoot = {}
  const singles: Record<number, keyof LogresMapRoot> = {
    1: 'Version',
    2: 'UpdateDate',
    3: 'Width',
    4: 'Height',
    6: 'FieldQuadUnitRow',
    7: 'FieldQuadUnitCol',
  }
  for (const field of readFields(data)) {
    const key = singles[field.number]
    if (key) singular(out as Record<string, unknown>, key, varint(field, `Root.${key}`))
    else if (field.number === 5) singular(out as Record<string, unknown>, 'QuadTreeRoot', decodeQuadTree(bytes(field, 'Root.QuadTreeRoot')))
    else throw new Error(`Root: unknown field ${field.number}:${field.wireType}`)
  }
  return out
}

export function flattenLogresMapGrids(root: LogresMapRoot): LogresMapGrid[] {
  const result: LogresMapGrid[] = []
  const walk = (tree: LogresMapQuadTree) => {
    result.push(...tree.Grids)
    tree.QuadTrees.forEach(walk)
  }
  if (root.QuadTreeRoot) walk(root.QuadTreeRoot)
  return result
}

export function logresMapSafeInt(value: bigint | undefined, label: string): number | undefined {
  if (value === undefined) return undefined
  if (value > BigInt(Number.MAX_SAFE_INTEGER)) {
    throw new Error(`${label} exceeds JavaScript safe integer range`)
  }
  return Number(value)
}
