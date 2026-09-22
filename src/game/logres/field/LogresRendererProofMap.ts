import {
  decodeLogresMap,
  flattenLogresMapGrids,
  logresMapSafeInt,
  type LogresMapRoot,
} from './LogresMapBinary'
import {
  fetchLogresRendererProofMap,
  LOGRES_RENDERER_PROOF_MAP_ID,
  LOGRES_RENDERER_PROOF_ROLE,
  logresRendererProofAssetUrls,
  type LogresRendererProofAssetUrls,
} from './LogresRendererProofAssets'

export interface LoadedLogresRendererProofMap {
  mapId: typeof LOGRES_RENDERER_PROOF_MAP_ID
  role: typeof LOGRES_RENDERER_PROOF_ROLE
  root: LogresMapRoot
  gridCount: number
  width: number
  height: number
  fieldQuadUnitRow: number
  fieldQuadUnitCol: number
}

/**
 * CONFIRMED ORIGINAL renderer-proof envelope for 001_000_00002.
 *
 * These values were recovered independently from the original .map payload and
 * are used here only as an integrity guard. They do not identify tutorial/start
 * behavior and do not define camera or projection semantics.
 */
export const LOGRES_RENDERER_PROOF_ENVELOPE = Object.freeze({
  width: 120,
  height: 120,
  fieldQuadUnitRow: 8,
  fieldQuadUnitCol: 8,
})

function requireSafe(
  value: bigint | undefined,
  label: string,
): number {
  const result = logresMapSafeInt(value, label)
  if (result === undefined) {
    throw new Error(`Renderer-proof map is missing ${label}`)
  }
  return result
}

export function validateLogresRendererProofMap(
  root: LogresMapRoot,
): Omit<LoadedLogresRendererProofMap, 'mapId' | 'role' | 'root'> {
  const width = requireSafe(root.Width, 'Width')
  const height = requireSafe(root.Height, 'Height')
  const fieldQuadUnitRow = requireSafe(root.FieldQuadUnitRow, 'FieldQuadUnitRow')
  const fieldQuadUnitCol = requireSafe(root.FieldQuadUnitCol, 'FieldQuadUnitCol')

  const expected = LOGRES_RENDERER_PROOF_ENVELOPE
  if (
    width !== expected.width ||
    height !== expected.height ||
    fieldQuadUnitRow !== expected.fieldQuadUnitRow ||
    fieldQuadUnitCol !== expected.fieldQuadUnitCol
  ) {
    throw new Error(
      `Renderer-proof map envelope mismatch: ${width}x${height}, quad ${fieldQuadUnitRow}x${fieldQuadUnitCol}`,
    )
  }

  return {
    width,
    height,
    fieldQuadUnitRow,
    fieldQuadUnitCol,
    gridCount: flattenLogresMapGrids(root).length,
  }
}

export async function loadLogresRendererProofMap(
  fetchImpl: typeof fetch = fetch,
  urls: LogresRendererProofAssetUrls = logresRendererProofAssetUrls(),
): Promise<LoadedLogresRendererProofMap> {
  const payload = await fetchLogresRendererProofMap(fetchImpl, urls)
  const root = decodeLogresMap(payload)
  const validated = validateLogresRendererProofMap(root)
  return {
    mapId: LOGRES_RENDERER_PROOF_MAP_ID,
    role: LOGRES_RENDERER_PROOF_ROLE,
    root,
    ...validated,
  }
}
