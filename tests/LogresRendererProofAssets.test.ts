import { describe, expect, it } from 'vitest'
import {
  fetchLogresRendererProofMap,
  LOGRES_RENDERER_PROOF_MAP_ID,
  LOGRES_RENDERER_PROOF_ROLE,
  logresRendererProofAssetUrls,
} from '../src/game/logres/field/LogresRendererProofAssets'

describe('private renderer-proof asset bridge', () => {
  it('uses the authentic proof map without claiming tutorial provenance', () => {
    expect(LOGRES_RENDERER_PROOF_MAP_ID).toBe('001_000_00002')
    expect(LOGRES_RENDERER_PROOF_ROLE).toBe('RENDERER_PROOF_NOT_TUTORIAL_MAP')
    expect(logresRendererProofAssetUrls('/proof/').mapBinary).toBe('/proof/001_000_00002.map.bin')
  })

  it('fetches the hydrated map payload and rejects missing private assets', async () => {
    const bytes = Uint8Array.from([1,2,3])
    const goodFetch = (async () => new Response(bytes, { status: 200 })) as typeof fetch
    await expect(fetchLogresRendererProofMap(goodFetch, logresRendererProofAssetUrls('/proof')))
      .resolves.toEqual(bytes)

    const badFetch = (async () => new Response(null, { status: 404 })) as typeof fetch
    await expect(fetchLogresRendererProofMap(badFetch, logresRendererProofAssetUrls('/proof')))
      .rejects.toThrow(/HTTP 404/)
  })
})
