import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_REFERENCE_DATA,
} from '../src/game/logres/ReferenceCatalog'

import {
  validateMasterData,
} from '../src/game/logres/MasterDataValidator'

describe(
  'Logres reconstruction foundation',
  () => {
    it(
      'contains the five reference starter jobs',
      () => {
        expect(
          LOGRES_REFERENCE_DATA.jobs
            .map((job) => job.id),
        ).toEqual([
          'fighter',
          'knight',
          'ranger',
          'priest',
          'mage',
        ])
      },
    )

    it(
      'has valid master-data references',
      () => {
        const result =
          validateMasterData(
            LOGRES_REFERENCE_DATA,
          )

        expect(
          result.errors,
        ).toEqual([])

        expect(
          result.valid,
        ).toBe(true)
      },
    )

    it(
      'marks placeholder balance data as reconstructed',
      () => {
        for (
          const job of
            LOGRES_REFERENCE_DATA.jobs
        ) {
          expect(
            job.provenance,
          ).toBe(
            'reconstructed',
          )
        }
      },
    )
  },
)
