import {
  describe,
  expect,
  it,
} from "vitest"

import {
  LOGRES_DEMO01_GRANT_KEY,
  LOGRES_DEMO01_REWARD_ITEM_KEY,
  completeReconstructedLogresDemoBattle,
} from "../src/game/logres/battle/ReconstructedLogresDemoBattleLoop"

describe(
  "ReconstructedLogresDemoBattleLoop",
  () => {
    it(
      "completes reconstructed battle -> reward -> inventory -> field-return-ready",
      () => {
        const result =
          completeReconstructedLogresDemoBattle()

        expect(
          result.provenance,
        ).toBe(
          "RECONSTRUCTED",
        )

        expect(
          result.flow.phase,
        ).toBe(
          "field-return-ready",
        )

        expect(
          result.rewardApplied,
        ).toBe(
          true,
        )

        expect(
          result.inventory.revision,
        ).toBe(
          1,
        )

        expect(
          result.inventory.entries,
        ).toEqual([
          expect.objectContaining({
            itemKey:
              LOGRES_DEMO01_REWARD_ITEM_KEY,
            originalItemId:
              null,
            quantity:
              1,
            grantKey:
              LOGRES_DEMO01_GRANT_KEY,
          }),
        ])
      },
    )

    it(
      "keeps the reconstruction-local grant idempotent",
      () => {
        const first =
          completeReconstructedLogresDemoBattle()

        const retry =
          completeReconstructedLogresDemoBattle(
            first.inventory,
          )

        expect(
          retry.rewardApplied,
        ).toBe(
          false,
        )

        expect(
          retry.inventory.revision,
        ).toBe(
          1,
        )

        expect(
          retry.inventory.entries,
        ).toHaveLength(
          1,
        )
      },
    )
  },
)
