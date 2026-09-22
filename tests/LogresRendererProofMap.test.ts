import { describe, expect, it } from 'vitest'
import {
  LOGRES_RENDERER_PROOF_ENVELOPE,
  loadLogresRendererProofMap,
  validateLogresRendererProofMap,
} from '../src/game/logres/field/LogresRendererProofMap'
import type { LogresMapRoot } from '../src/game/logres/field/LogresMapBinary'
import { logresRendererProofAssetUrls } from '../src/game/logres/field/LogresRendererProofAssets'

describe('renderer-proof runtime map loader', () => {
  it('validates the confirmed original renderer-proof envelope without tutorial claims', () => {
    const root: LogresMapRoot = {
      Width: 120n,
      Height: 120n,
      FieldQuadUnitRow: 8n,
      FieldQuadUnitCol: 8n,
      QuadTreeRoot: { Grids: [], QuadTrees: [] },
    }
    expect(validateLogresRendererProofMap(root)).toEqual({
      ...LOGRES_RENDERER_PROOF_ENVELOPE,
      gridCount: 0,
    })
  })

  it('rejects a mismatched map envelope', () => {
    expect(() => validateLogresRendererProofMap({
      Width: 121n,
      Height: 120n,
      FieldQuadUnitRow: 8n,
      FieldQuadUnitCol: 8n,
    })).toThrow(/envelope mismatch/)
  })

  it('fetches and decodes the authentic wire schema through the private proof bridge', async () => {
    const bytes = Uint8Array.from([
      0x18, 0x78, // Width = 120
      0x20, 0x78, // Height = 120
      0x30, 0x08, // FieldQuadUnitRow = 8
      0x38, 0x08, // FieldQuadUnitCol = 8
    ])
    const fakeFetch = (async () => new Response(bytes, { status: 200 })) as typeof fetch
    const loaded = await loadLogresRendererProofMap(
      fakeFetch,
      logresRendererProofAssetUrls('/proof'),
    )
    expect(loaded.mapId).toBe('001_000_00002')
    expect(loaded.role).toBe('RENDERER_PROOF_NOT_TUTORIAL_MAP')
    expect(loaded.width).toBe(120)
  })
})
