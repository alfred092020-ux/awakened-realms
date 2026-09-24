import fs from 'node:fs'
import path from 'node:path'
import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
} from '../src/game/logres/encounter/LogresGlobalEncounterNativeEvidence'

import {
  ReconstructedLogresEncounterAuthority,
} from '../src/game/logres/encounter/ReconstructedLogresEncounterAuthority'

import {
  GLOBAL_BEHAVIOR_TRANSITIONS,
  LogresGlobalBehaviorTwin,
  compareBehaviorTrace,
  serverAuthorityStub,
  type ImplementationTraceStep,
} from '../src/game/logres/reverse/LogresGlobalBehaviorTwin'

import {
  LOGRES_GLOBAL_DIFFERENTIAL_COUNTS,
  LOGRES_GLOBAL_DIFFERENTIAL_HISTORICAL_IMPLEMENTATION_BUGS,
  LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS,
  LOGRES_GLOBAL_DIFFERENTIAL_REPAIRED_FINDINGS,
} from '../src/game/logres/reverse/LogresGlobalDifferentialEvidence'

function eligible() {
  return {
    globalEncounterAllowed:
      true,
    encounterEnabled:
      true,
    entryStateEligible:
      true,
    questAllowsEncounter:
      true,
    distanceEligible:
      true,
  }
}

describe(
  'current Logres behavioral fidelity coverage',
  () => {
    it(
      'preserves historical bug findings while current status reports both repaired',
      () => {
        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_HISTORICAL_IMPLEMENTATION_BUGS
            .map(
              finding =>
                finding.id,
            ),
        ).toEqual([
          'battle-entry-retry-gate-enforcement',
          'playable-field-battle-entry-wiring',
        ])

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_REPAIRED_FINDINGS
            .every(
              finding =>
                finding.currentStatus ===
                'VERIFIED_REPAIRED',
            ),
        ).toBe(
          true,
        )

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS,
        ).toEqual([])

        expect(
          LOGRES_GLOBAL_DIFFERENTIAL_COUNTS,
        ).toMatchObject({
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
        })
      },
    )

    it(
      'proves the exact recovered one-second retry gate against current runtime code',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'fidelity-retry',
            areaRef:
              null,
            symbolRef:
              null,
            mapPosition:
              null,
            rawEntryState:
              null,
            eligibility:
              eligible(),
          })

        authority.createBattleEntryIntent()

        authority.recordBattleEntryResponse({
          rawCode:
            2,
        })

        expect(
          authority.snapshot()
            .retryDelaySeconds,
        ).toBe(
          LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
        )

        expect(
          () =>
            authority.createBattleEntryIntent(),
        ).toThrow(
          'retry wait has not elapsed',
        )

        authority.elapseRetryDelay(
          LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
        )

        expect(
          authority.createBattleEntryIntent()
            .encounterKey,
        ).toBe(
          'fidelity-retry',
        )
      },
    )

    it(
      'proves playable-field source keeps request -> response -> initialize ordering',
      () => {
        const source =
          fs.readFileSync(
            path.resolve(
              process.cwd(),
              'src/game/logres/field/controllers/LogresFieldEncounterController.ts',
            ),
            'utf8',
          )

        const request =
          source.indexOf(
            'bridge.requestEntry()',
          )

        const response =
          source.indexOf(
            'bridge.recordEntryResponse({',
          )

        const initialized =
          source.indexOf(
            'bridge.recordBattleInitialized({',
          )

        expect(
          request,
        ).toBeGreaterThanOrEqual(
          0,
        )

        expect(
          response,
        ).toBeGreaterThan(
          request,
        )

        expect(
          initialized,
        ).toBeGreaterThan(
          response,
        )

        expect(
          source,
        ).toContain(
          "'RECONSTRUCTED_SERVER_AUTHORITY_STUB' as const",
        )
      },
    )

    it(
      'projects the recovered battle loop into an evidence-bounded implementation trace',
      () => {
        const twin =
          new LogresGlobalBehaviorTwin({
            initialState:
              'AREA_ACTIVE',
          })

        twin.receiveEnemyAppear(
          serverAuthorityStub(
            {},
            'retired enemy payload unresolved',
          ),
        )

        twin.requestBattleEntry()

        twin.receiveBattleEntry(
          serverAuthorityStub(
            1,
            'retired server outcome reconstructed to exercise confirmed accepted client branch',
          ),
        )

        twin.receiveBattleInitialize(
          serverAuthorityStub(
            {},
            'retired battle initialization payload unresolved',
          ),
        )

        twin.receiveBoutInitialize(
          serverAuthorityStub(
            {},
            'retired bout payload unresolved',
          ),
        )

        twin.requestUseSkill()

        twin.receiveBattleResult(
          serverAuthorityStub(
            {},
            'retired result payload unresolved',
          ),
        )

        twin.receiveQuestResult(
          serverAuthorityStub(
            {},
            'retired reward payload unresolved',
          ),
        )

        twin.receiveQuestReturn(
          serverAuthorityStub(
            {},
            'retired return payload unresolved',
          ),
        )

        twin.resumeField()

        const observed:
          ImplementationTraceStep[] =
          twin.trace.map(
            step => ({
              from:
                step.from,
              to:
                step.to,
              message:
                step.message,
              event:
                step.event,
              serverAuthorityClaim:
                step.serverAuthority
                  ? 'SERVER_STUB'
                  : 'CLIENT_PROJECTION',
            }),
          )

        const comparison =
          compareBehaviorTrace(
            twin.trace,
            observed,
          )

        expect(
          comparison,
        ).toEqual({
          pass:
            true,
          mismatches:
            [],
        })

        expect(
          twin.state,
        ).toBe(
          'AREA_ACTIVE',
        )

        expect(
          twin.trace
            .filter(
              step =>
                step.serverAuthority,
            )
            .every(
              step =>
                Boolean(
                  step.stubEvidenceCeiling,
                ),
            ),
        ).toBe(
          true,
        )

        expect(
          GLOBAL_BEHAVIOR_TRANSITIONS,
        ).toHaveLength(
          28,
        )
      },
    )

    it(
      'detects a critical ordering divergence instead of normalizing it away',
      () => {
        const expected =
          new LogresGlobalBehaviorTwin({
            initialState:
              'ENCOUNTER_ELIGIBILITY',
          })

        expected.requestBattleEntry()

        expected.receiveBattleEntry(
          serverAuthorityStub(
            1,
            'accepted branch fixture',
          ),
        )

        const actual:
          ImplementationTraceStep[] = [
            {
              from:
                'ENCOUNTER_ELIGIBILITY',
              to:
                'BATTLE_ENTRY_PENDING',
              message:
                'C_GMCL_BATTLE_ENTRY_REQ',
              serverAuthorityClaim:
                'CLIENT_PROJECTION',
            },
            {
              from:
                'BATTLE_ENTRY_PENDING',
              to:
                'BATTLE_INITIALIZING',
              message:
                'S_GMCL_BATTLE_INITIALIZE',
              serverAuthorityClaim:
                'SERVER_STUB',
            },
          ]

        const result =
          compareBehaviorTrace(
            expected.trace,
            actual,
          )

        expect(
          result.pass,
        ).toBe(
          false,
        )

        expect(
          result.mismatches.join(
            '\n',
          ),
        ).toContain(
          'step 1',
        )
      },
    )
  },
)
