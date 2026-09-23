export type LogresMapInfoKind =
  | 'chip'
  | 'object'

export interface LogresMapInfoRecord {
  /**
   * CONFIRMED ORIGINAL MultiID packed uint32 representation.
   *
   * Native MultiID(u8, u8, u16) stores the first component in bits 31..24,
   * the second in bits 23..16, and the final uint16 in bits 15..0.
   */
  packedId: number

  /**
   * Raw components read from the fixed map-info record.
   *
   * Their game-domain names have not been recovered, so they remain neutral.
   */
  component0: number
  component1: number
  component2: number

  /**
   * Byte copied to InfoChipBin/InfoObjectBin offset 0x18 by the native
   * MapInfoResource loader. Native field code later reads this byte as height.
   */
  height: number

  /**
   * CONFIRMED ORIGINAL in current native InfoObjectBin semantics:
   * byte 0x19 is the structure footprint along native adjacency 7
   * (-col), and byte 0x1a is the footprint along native adjacency 1
   * (-row).
   *
   * Present only for MAP_OBJECT records.
   */
  structureFootprintCols?: number
  structureFootprintRows?: number

  /**
   * Raw InfoObjectBin bytes. Current native setup treats exactly value 1 as
   * true for these booleans.
   */
  structureClimbableFlag?: number
  structureSwfFlag?: number

  recordIndex: number
}

export interface LogresMapInfoTable {
  kind: LogresMapInfoKind
  formatWordLow16: number
  recordCount: number
  records:
    readonly Readonly<
      LogresMapInfoRecord
    >[]
  byPackedId:
    ReadonlyMap<
      number,
      Readonly<
        LogresMapInfoRecord
      >
    >
}

const HEADER_SIZE =
  0x14

const HEIGHT_OFFSET =
  0x18

const OBJECT_FOOTPRINT_COLS_OFFSET =
  0x19

const OBJECT_FOOTPRINT_ROWS_OFFSET =
  0x1a

const OBJECT_CLIMBABLE_OFFSET =
  0x1b

const OBJECT_SWF_OFFSET =
  0x1c

const SPEC = {
  chip: {
    magic:
      'MAP_CHIP',
    recordSize:
      0x28,
  },
  object: {
    magic:
      'MAP_OBJECT',
    recordSize:
      0x2a,
  },
} as const

function dataView(
  data: Uint8Array,
): DataView {
  return new DataView(
    data.buffer,
    data.byteOffset,
    data.byteLength,
  )
}

function requireMagic(
  data: Uint8Array,
  magic: string,
) {
  if (
    data.byteLength <
    HEADER_SIZE
  ) {
    throw new Error(
      'Logres map-info payload is truncated',
    )
  }

  for (
    let index = 0;
    index < magic.length;
    index += 1
  ) {
    if (
      data[index] !==
      magic.charCodeAt(
        index,
      )
    ) {
      throw new Error(
        `Unexpected Logres map-info magic; expected ${magic}`,
      )
    }
  }

  for (
    let index =
      magic.length;
    index <
      0x0c;
    index += 1
  ) {
    if (
      data[index] !==
      0
    ) {
      throw new Error(
        'Logres map-info magic padding is non-zero',
      )
    }
  }
}

/**
 * CONFIRMED ORIGINAL MultiID memory layout from native constructors.
 */
export function logresMultiIdFromComponents(
  component0: number,
  component1: number,
  component2: number,
): number {
  if (
    !Number.isInteger(
      component0,
    ) ||
    component0 < 0 ||
    component0 > 0xff ||
    !Number.isInteger(
      component1,
    ) ||
    component1 < 0 ||
    component1 > 0xff ||
    !Number.isInteger(
      component2,
    ) ||
    component2 < 0 ||
    component2 > 0xffff
  ) {
    throw new Error(
      'Invalid Logres MultiID components',
    )
  }

  return (
    component0 *
      0x1000000 +
    component1 *
      0x10000 +
    component2
  )
}

/**
 * Parses one original Logres MAP_CHIP or MAP_OBJECT metadata table.
 *
 * Current native MapInfoResource evidence establishes:
 * - 0x14-byte header
 * - record count in header word high 16 bits
 * - 0x28-byte InfoChipBin records
 * - 0x2a-byte InfoObjectBin records
 * - fixed records copied byte-for-byte into the native Info*Bin value
 *
 * Recovered May-2017 Global tables conform exactly to these sizes/counts.
 * Applying later native field semantics to those Global records remains a
 * separately labelled evidence decision; this parser only preserves bytes
 * proven by the common binary layout.
 */
export function parseLogresMapInfoTable(
  data: Uint8Array,
  kind: LogresMapInfoKind,
): LogresMapInfoTable {
  const spec =
    SPEC[
      kind
    ]

  requireMagic(
    data,
    spec.magic,
  )

  const view =
    dataView(
      data,
    )

  const countAndFormat =
    view.getUint32(
      0x10,
      true,
    )

  const recordCount =
    countAndFormat >>>
    16

  const formatWordLow16 =
    countAndFormat &
    0xffff

  const expectedLength =
    HEADER_SIZE +
    recordCount *
      spec.recordSize

  if (
    data.byteLength !==
    expectedLength
  ) {
    throw new Error(
      `Logres ${kind} map-info length mismatch: expected ${expectedLength}, got ${data.byteLength}`,
    )
  }

  const records:
    Readonly<
      LogresMapInfoRecord
    >[] = []

  const byPackedId =
    new Map<
      number,
      Readonly<
        LogresMapInfoRecord
      >
    >()

  for (
    let recordIndex = 0;
    recordIndex <
      recordCount;
    recordIndex += 1
  ) {
    const offset =
      HEADER_SIZE +
      recordIndex *
        spec.recordSize

    const component0 =
      data[
        offset
      ]!

    const component1 =
      data[
        offset +
          1
      ]!

    const component2 =
      view.getUint16(
        offset +
          2,
        true,
      )

    const packedId =
      logresMultiIdFromComponents(
        component0,
        component1,
        component2,
      )

    if (
      byPackedId.has(
        packedId,
      )
    ) {
      throw new Error(
        `Duplicate Logres map-info MultiID: ${packedId}`,
      )
    }

    const record:
      Readonly<
        LogresMapInfoRecord
      > =
      Object.freeze({
        packedId,
        component0,
        component1,
        component2,
        height:
          data[
            offset +
              HEIGHT_OFFSET
          ]!,
        ...(
          kind ===
            'object'
            ? {
                structureFootprintCols:
                  data[
                    offset +
                      OBJECT_FOOTPRINT_COLS_OFFSET
                  ]!,
                structureFootprintRows:
                  data[
                    offset +
                      OBJECT_FOOTPRINT_ROWS_OFFSET
                  ]!,
                structureClimbableFlag:
                  data[
                    offset +
                      OBJECT_CLIMBABLE_OFFSET
                  ]!,
                structureSwfFlag:
                  data[
                    offset +
                      OBJECT_SWF_OFFSET
                  ]!,
              }
            : {}
        ),
        recordIndex,
      })

    records.push(
      record,
    )

    byPackedId.set(
      packedId,
      record,
    )
  }

  return {
    kind,
    formatWordLow16,
    recordCount,
    records:
      Object.freeze(
        records,
      ),
    byPackedId,
  }
}

export function logresMapInfoHeight(
  table: LogresMapInfoTable,
  packedId: number,
): number | undefined {
  if (
    !Number.isSafeInteger(
      packedId,
    ) ||
    packedId < 0 ||
    packedId >
      0xffffffff
  ) {
    throw new Error(
      'Logres packed MultiID must be an unsigned uint32',
    )
  }

  return table
    .byPackedId
    .get(
      packedId,
    )
    ?.height
}

export interface LogresMapInfoObjectStructure {
  height: number
  footprintCols: number
  footprintRows: number
  climbable: boolean
  swf: boolean
}

/**
 * Returns the movement-relevant native InfoObjectBin structure fields.
 *
 * Current-JP native evidence establishes:
 * - record byte 0x18 contributes structure height
 * - byte 0x19 is the -col footprint count
 * - byte 0x1a is the -row footprint count
 * - byte 0x1b == 1 is FieldStructure::isClimbable()
 * - byte 0x1c == 1 is FieldStructure::getIsSwf()
 *
 * Recovered May-2017 Global MAP_OBJECT records use the same fixed envelope.
 * Applying the later native semantics to Global remains a separately labelled
 * SUPPORTED INFERENCE in the navigation model.
 */
export function logresMapInfoObjectStructure(
  table: LogresMapInfoTable,
  packedId: number,
):
  | Readonly<
      LogresMapInfoObjectStructure
    >
  | undefined {
  if (
    table.kind !==
    'object'
  ) {
    throw new Error(
      'Logres object structure metadata requires MAP_OBJECT table',
    )
  }

  if (
    !Number.isSafeInteger(
      packedId,
    ) ||
    packedId < 0 ||
    packedId >
      0xffffffff
  ) {
    throw new Error(
      'Logres packed MultiID must be an unsigned uint32',
    )
  }

  const record =
    table.byPackedId.get(
      packedId,
    )

  if (!record) {
    return undefined
  }
  const footprintCols =
    record
      .structureFootprintCols

  const footprintRows =
    record
      .structureFootprintRows

  const climbableFlag =
    record
      .structureClimbableFlag

  const swfFlag =
    record
      .structureSwfFlag

  if (
    footprintCols ===
      undefined ||
    footprintRows ===
      undefined ||
    climbableFlag ===
      undefined ||
    swfFlag ===
      undefined
  ) {
    throw new Error(
      'Logres MAP_OBJECT record is missing structure footprint fields',
    )
  }

  return Object.freeze({
    height:
      record.height,
    footprintCols,
    footprintRows,
    climbable:
      climbableFlag ===
      1,
    swf:
      swfFlag ===
      1,
  })
}
