/**
 * Private renderer-proof asset descriptor.
 *
 * CONFIRMED ORIGINAL:
 * - map id/package pairing
 * - decompressed .map payload
 * - A4R4G4B4 CHIP/OBJ source textures
 *
 * The files themselves are private/gitignored development derivatives and must
 * be hydrated separately. This module does not claim the map is the tutorial map.
 */
export const LOGRES_RENDERER_PROOF_MAP_ID = '001_000_00002' as const
export const LOGRES_RENDERER_PROOF_ROLE = 'RENDERER_PROOF_NOT_TUTORIAL_MAP' as const

export interface LogresRendererProofAssetUrls {
  mapBinary: string
  chipPng: string
  objPng: string
  metadata: string
}

export function logresRendererProofAssetUrls(
  root = '/__logres_ref/renderer-proof/001_000_00002',
): LogresRendererProofAssetUrls {
  const base = root.replace(/\/$/, '')
  return {
    mapBinary: `${base}/001_000_00002.map.bin`,
    chipPng: `${base}/001_000_00002_CHIP.png`,
    objPng: `${base}/001_000_00002_OBJ.png`,
    metadata: `${base}/metadata.json`,
  }
}

export async function fetchLogresRendererProofMap(
  fetchImpl: typeof fetch = fetch,
  urls = logresRendererProofAssetUrls(),
): Promise<Uint8Array> {
  const response = await fetchImpl(urls.mapBinary)
  if (!response.ok) {
    throw new Error(`Renderer-proof map unavailable: HTTP ${response.status}`)
  }
  return new Uint8Array(await response.arrayBuffer())
}
