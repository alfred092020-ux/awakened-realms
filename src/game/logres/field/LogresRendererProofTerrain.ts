import {
  loadLogresRendererProofMap,
  type LoadedLogresRendererProofMap,
} from './LogresRendererProofMap'
import {
  extractLogresTerrainPrimitives,
  type LogresTerrainPrimitiveSet,
} from './LogresTerrainPrimitives'
import {
  logresRendererProofAssetUrls,
  type LogresRendererProofAssetUrls,
} from './LogresRendererProofAssets'

export interface LoadedLogresRendererProofTerrain {
  map: LoadedLogresRendererProofMap
  terrain: LogresTerrainPrimitiveSet
  textures: {
    chipPng: string
    objPng: string
  }
}

export function composeLogresRendererProofTerrain(
  map: LoadedLogresRendererProofMap,
  urls: LogresRendererProofAssetUrls = logresRendererProofAssetUrls(),
): LoadedLogresRendererProofTerrain {
  return {
    map,
    terrain: extractLogresTerrainPrimitives(map.root),
    textures: {
      chipPng: urls.chipPng,
      objPng: urls.objPng,
    },
  }
}

/**
 * Runtime composition only. This makes the authentic proof map and its original
 * CHIP/OBJ geometry available to the renderer, but intentionally does not choose
 * final Z, projection, camera transform, UV orientation, or tutorial semantics.
 */
export async function loadLogresRendererProofTerrain(
  fetchImpl: typeof fetch = fetch,
  urls: LogresRendererProofAssetUrls = logresRendererProofAssetUrls(),
): Promise<LoadedLogresRendererProofTerrain> {
  const map = await loadLogresRendererProofMap(fetchImpl, urls)
  return composeLogresRendererProofTerrain(map, urls)
}
