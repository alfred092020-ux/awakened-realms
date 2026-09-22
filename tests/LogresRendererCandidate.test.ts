import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  loadLogresRendererCandidate,
  logresRendererCandidateUrls,
  LOGRES_RENDERER_CANDIDATE_ROLE,
  requireLogresMapId,
} from '../src/game/logres/field/LogresRendererCandidate'

describe(
  'Logres renderer candidate loader',
  () => {
    it(
      'builds private candidate URLs without assigning tutorial identity',
      () => {
        expect(
          logresRendererCandidateUrls(
            '001_000_00001',
            '/proof/',
          ),
        ).toEqual({
          mapBinary:
            '/proof/001_000_00001/001_000_00001.map.bin',
          chipPng:
            '/proof/001_000_00001/001_000_00001_CHIP.png',
          objPng:
            '/proof/001_000_00001/001_000_00001_OBJ.png',
          metadata:
            '/proof/001_000_00001/metadata.json',
        })

        expect(
          LOGRES_RENDERER_CANDIDATE_ROLE,
        ).toBe(
          'CANDIDATE_NOT_IDENTIFIED_TUTORIAL',
        )
      },
    )

    it(
      'rejects malformed map identifiers',
      () => {
        expect(
          () =>
            requireLogresMapId(
              '../private',
            ),
        ).toThrow(
          'Invalid Logres map id',
        )
      },
    )

    it(
      'decodes a candidate map without fixed proof-envelope assumptions',
      async () => {
        const bytes =
          Uint8Array.from([
            0x18, 0x10,
            0x20, 0x20,
            0x30, 0x08,
            0x38, 0x08,
          ])

        const fakeFetch =
          (async () =>
            new Response(
              bytes,
              {
                status: 200,
              },
            )) as
            typeof fetch

        const loaded =
          await loadLogresRendererCandidate(
            '001_000_00001',
            fakeFetch,
            logresRendererCandidateUrls(
              '001_000_00001',
              '/proof',
            ),
          )

        expect(
          loaded.mapId,
        ).toBe(
          '001_000_00001',
        )
        expect(
          loaded.gridCount,
        ).toBe(0)
        expect(
          loaded.terrain.primitives,
        ).toEqual([])
      },
    )
  },
)
