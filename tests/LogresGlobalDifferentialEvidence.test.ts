import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT,
  LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT_SHA256,
  LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES,
  LOGRES_GLOBAL_DIFFERENTIAL_COUNTS,
  LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS,
  LOGRES_GLOBAL_DIFFERENTIAL_HISTORICAL_IMPLEMENTATION_BUGS,
  LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS,
  LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES,
  LOGRES_GLOBAL_DIFFERENTIAL_REPAIRED_FINDINGS,
  LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET,
} from '../src/game/logres/reverse/LogresGlobalDifferentialEvidence'

describe(
  'Global differential evidence status',
  () => {
    it(
      'preserves the original nine checks while separating current repairs from historical findings',
      () => {
        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_COUNTS,
        ).toEqual({
          checks:
            9,
          pass:
            7,
          implementationBugs:
            0,
          repairedBugs:
            2,
          intentionalServerStubs:
            1,
          unknown:
            1,
          divergences:
            2,
          fuzzerCasesAvailable:
            109,
        })

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_HISTORICAL_IMPLEMENTATION_BUGS,
        ).toHaveLength(
          2,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIRED_FINDINGS,
        ).toHaveLength(
          2,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS,
        ).toHaveLength(
          0,
        )
      },
    )

    it(
      'promotes both repaired findings into the current confirmed pass set',
      () => {
        const ids =
          LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES
            .map(
              item =>
                item.id,
            )

        expect(
          ids,
        ).toContain(
          'battle-entry-retry-gate-enforcement',
        )

        expect(
          ids,
        ).toContain(
          'playable-field-battle-entry-wiring',
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES,
        ).toHaveLength(
          7,
        )
      },
    )

    it(
      'keeps server-stub and unknown reward behavior separate from repaired bugs',
      () => {
        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES,
        ).toHaveLength(
          2,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES[0]
            .classification,
        ).toBe(
          'INTENTIONAL_SERVER_STUB',
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES[1]
            .classification,
        ).toBe(
          'UNKNOWN',
        )
      },
    )

    it(
      'retains the bounded repair packet as verified historical closure rather than auto authority',
      () => {
        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET
            .status,
        ).toBe(
          'VERIFIED_REPAIRED',
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET
            .autoApply,
        ).toBe(
          false,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET
            .autoMerge,
        ).toBe(
          false,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET
            .acceptance,
        ).toContain(
          'Response code 2 must block another entry request until exactly 1.0 second elapses.',
        )
      },
    )

    it(
      'preserves evidence ceilings and immutable artifact identity',
      () => {
        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS,
        ).toContain(
          'Historical findings remain preserved after repair rather than being rewritten as if they never existed.',
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS,
        ).toContain(
          'Unknown retired-server semantics remain UNKNOWN rather than being filled from current JP.',
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_COUNTS
            .fuzzerCasesAvailable,
        ).toBe(
          109,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT_SHA256,
        ).toHaveLength(
          64,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT,
        ).toContain(
          'global3024-differential-emulator',
        )
      },
    )
  },
)
