import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE,
  ReconstructedLogresEncounterAuthority,
} from '../src/game/logres/encounter/ReconstructedLogresEncounterAuthority'

import {
  LOGRES_GLOBAL_3024_ENCOUNTER_NATIVE_PROVENANCE,
  LOGRES_GLOBAL_BATTLE_ENTRY_GATE_ORDER,
  LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
  logresGlobalBattleEntryResponseMeaning,
} from '../src/game/logres/encounter/LogresGlobalEncounterNativeEvidence'

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
  'reconstructed Logres encounter authority',
  () => {
    it(
      'locks the confirmed Global 3.0.24 encounter gate order and only resolved response meanings',
      () => {
        expect(
          LOGRES_GLOBAL_BATTLE_ENTRY_GATE_ORDER,
        ).toEqual([
          'GLOBAL_ENCOUNTER_ALLOWED',
          'ENCOUNTER_ENABLED',
          'ENTRY_NOT_ALREADY_ACCEPTED',
          'ENCOUNTER_STATE_PRESENT',
          'RETRY_WAIT_ELAPSED_AND_REQUEST_NOT_PENDING',
          'ENTRY_STATE_ELIGIBLE',
          'QUEST_STATE_ELIGIBLE',
          'DISTANCE_TO_SELF_PLAYER_ELIGIBLE',
          'REQUEST_BATTLE_ENTRY',
        ])

        expect(
          logresGlobalBattleEntryResponseMeaning(
            1,
          ),
        ).toBe(
          'ENTRY_ACCEPTED',
        )

        expect(
          logresGlobalBattleEntryResponseMeaning(
            2,
          ),
        ).toBe(
          'RETRY_WAIT_1_SECOND',
        )

        expect(
          logresGlobalBattleEntryResponseMeaning(
            0,
          ),
        ).toBe(
          'UNRESOLVED',
        )
      },
    )

    it(
      'keeps original field identifiers nullable while creating a local battle-entry intent',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'tutorial-encounter',
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

        expect(
          authority.createBattleEntryIntent(),
        ).toEqual({
          provenance:
            LOGRES_RECONSTRUCTED_ENCOUNTER_PROVENANCE,
          encounterKey:
            'tutorial-encounter',
          areaRef:
            null,
          symbolRef:
            null,
          mapPosition:
            null,
          rawEntryState:
            null,
        })

        expect(
          authority.snapshot()
            .requestPending,
        ).toBe(
          true,
        )
      },
    )

    it(
      'requires every explicit eligibility gate without assuming the current-JP raw entry-state value is Global truth',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'blocked',
            areaRef:
              null,
            symbolRef:
              null,
            mapPosition:
              null,
            rawEntryState:
              0,
            eligibility: {
              ...eligible(),
              questAllowsEncounter:
                false,
            },
          })

        expect(
          () =>
            authority.createBattleEntryIntent(),
        ).toThrow(
          'questAllowsEncounter',
        )

        authority.updateEligibility(
          eligible(),
        )

        expect(
          authority.createBattleEntryIntent()
            .rawEntryState,
        ).toBe(
          0,
        )
      },
    )

    it(
      'applies the confirmed Global 3.0.24 one-second retry for response code 2',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
            areaRef:
              'area-a',
            symbolRef:
              'symbol-a',
            mapPosition: {
              x: 10,
              y: 20,
            },
            rawEntryState:
              0,
            eligibility:
              eligible(),
          })

        authority.createBattleEntryIntent()

        authority.recordBattleEntryResponse({
          rawCode:
            2,
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          lastResponseCode:
            2,
          retryDelaySeconds:
            LOGRES_GLOBAL_BATTLE_ENTRY_RETRY_SECONDS,
          entryAccepted:
            false,
          battleInitialized:
            false,
        })
      },
    )

    it(
      'marks response code 1 as the distinct confirmed Global entry-accepted state',
      () => {
        expect(
          LOGRES_GLOBAL_3024_ENCOUNTER_NATIVE_PROVENANCE,
        ).toBe(
          'CONFIRMED_GLOBAL_3_0_24_NATIVE',
        )

        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
            areaRef:
              null,
            symbolRef:
              null,
            mapPosition:
              null,
            rawEntryState:
              0,
            eligibility:
              eligible(),
          })

        authority.createBattleEntryIntent()

        authority.recordBattleEntryResponse({
          rawCode:
            1,
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          lastResponseCode:
            1,
          retryDelaySeconds:
            null,
          entryAccepted:
            true,
        })

        expect(
          authority.snapshot()
            .rawEntryState,
        ).toBe(
          0,
        )

        expect(
          () =>
            authority.createBattleEntryIntent(),
        ).toThrow(
          'already accepted',
        )
      },
    )

    it(
      'accepts externally supplied retry timing without treating it as original Global behavior',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
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
          retryDelaySeconds:
            1,
        })

        expect(
          authority.snapshot()
            .retryDelaySeconds,
        ).toBe(
          1,
        )

        authority.clearRetryDelay()

        expect(
          authority.snapshot()
            .retryDelaySeconds,
        ).toBeNull()
      },
    )

    it(
      'keeps collision-symbol observation separate from local battle entry',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
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

        authority.observeCollisionSymbol({
          areaRef:
            'area-a',
          symbolRef:
            'symbol-a',
          mapPosition: {
            x: 4,
            y: 8,
          },
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          battleInitialized:
            false,
          lastCollisionSymbol: {
            areaRef:
              'area-a',
            symbolRef:
              'symbol-a',
            mapPosition: {
              x: 4,
              y: 8,
            },
          },
        })
      },
    )

    it(
      'keeps party-member encounter involvement separate from the local players entry state',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
            areaRef:
              'area-a',
            symbolRef:
              'symbol-a',
            mapPosition: {
              x: 1,
              y: 2,
            },
            rawEntryState:
              null,
            eligibility:
              eligible(),
          })

        authority.observePartyMemberEncounter({
          areaRef:
            'area-a',
          symbolRef:
            'symbol-a',
          mapPosition: {
            x: 3,
            y: 4,
          },
          rawRangeOrRadius:
            250,
        })

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          battleInitialized:
            false,
          lastPartyEncounter: {
            rawRangeOrRadius:
              250,
          },
        })
      },
    )

    it(
      'lets authoritative battle initialization complete the transition independently from raw response-code meaning',
      () => {
        const authority =
          new ReconstructedLogresEncounterAuthority({
            encounterKey:
              'enemy-a',
            areaRef:
              'area-a',
            symbolRef:
              'symbol-a',
            mapPosition: {
              x: 1,
              y: 2,
            },
            rawEntryState:
              0,
            eligibility:
              eligible(),
          })

        authority.createBattleEntryIntent()

        authority.markBattleInitialized(
          'battle-system-a',
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          requestPending:
            false,
          battleInitialized:
            true,
          battleSystemRef:
            'battle-system-a',
        })

        expect(
          () =>
            authority.createBattleEntryIntent(),
        ).toThrow(
          'already initialized a battle',
        )
      },
    )
  },
)
