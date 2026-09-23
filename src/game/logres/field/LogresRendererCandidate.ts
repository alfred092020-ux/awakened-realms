import {
  decodeLogresMap,
  flattenLogresMapGrids,
  type LogresMapRoot,
} from './LogresMapBinary'
import {
  extractLogresTerrainPrimitives,
  type LogresTerrainPrimitiveSet,
} from './LogresTerrainPrimitives'

import {
  logresRuntimeUrl,
} from '../ui/LogresRuntimeAssets'

const MAP_ID_PATTERN =
  /^\d{3}_\d{3}_\d{5}$/

export const LOGRES_RENDERER_CANDIDATE_ROLE =
  'CANDIDATE_NOT_IDENTIFIED_TUTORIAL' as const

export interface LogresRendererCandidateUrls {
  mapBinary: string
  chipPng: string
  objPng: string
  metadata: string
}

export interface LoadedLogresRendererCandidate {
  mapId: string
  role: typeof LOGRES_RENDERER_CANDIDATE_ROLE
  root: LogresMapRoot
  gridCount: number
  terrain: LogresTerrainPrimitiveSet
  textures: {
    chipPng: string
    objPng: string
  }
}

export function requireLogresMapId(
  mapId: string,
): string {
  if (!MAP_ID_PATTERN.test(mapId)) {
    throw new Error(
      `Invalid Logres map id: ${mapId}`,
    )
  }
  return mapId
}

export function logresRendererCandidateUrls(
  mapId: string,
  root = '/__logres_ref/renderer-proof',
): LogresRendererCandidateUrls {
  const id = requireLogresMapId(mapId)
  const base =
    `${root.replace(/\/$/, '')}/${id}`

  return {
    mapBinary:
      logresRuntimeUrl(
        `${base}/${id}.map.bin`,
      ),
    chipPng:
      logresRuntimeUrl(
        `${base}/${id}_CHIP.png`,
      ),
    objPng:
      logresRuntimeUrl(
        `${base}/${id}_OBJ.png`,
      ),
    metadata:
      logresRuntimeUrl(
        `${base}/metadata.json`,
      ),
  }
}

/**
 * Diagnostic candidate loader only.
 *
 * CONFIRMED ORIGINAL data is decoded and rendered without assigning tutorial
 * identity. Candidate selection remains SUPPORTED INFERENCE until visual and
 * semantic evidence agree.
 */
export async function loadLogresRendererCandidate(
  mapId: string,
  fetchImpl: typeof fetch = fetch,
  urls = logresRendererCandidateUrls(mapId),
): Promise<LoadedLogresRendererCandidate> {
  requireLogresMapId(mapId)

  const response =
    await fetchImpl(urls.mapBinary)

  if (!response.ok) {
    throw new Error(
      `Renderer candidate unavailable: HTTP ${response.status}`,
    )
  }

  const root =
    decodeLogresMap(
      new Uint8Array(
        await response.arrayBuffer(),
      ),
    )

  return {
    mapId,
    role:
      LOGRES_RENDERER_CANDIDATE_ROLE,
    root,
    gridCount:
      flattenLogresMapGrids(root)
        .length,
    terrain:
      extractLogresTerrainPrimitives(root),
    textures: {
      chipPng:
        urls.chipPng,
      objPng:
        urls.objPng,
    },
  }
}
