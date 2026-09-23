import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  ReconstructedLogresEncounterAuthority,
} from '../src/game/logres/encounter/ReconstructedLogresEncounterAuthority'

import {
  LOGRES_BATTLE_SCENE_KEY,
  ReconstructedLogresBattleEntryBridge,
} from '../src/game/logres/encounter/ReconstructedLogresBattleEntryBridge'

function encounter() {
  return new ReconstructedLogresEncounterAuthority({
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
    eligibility: {
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
    },
  })
}

describe(
  'reconstructed encounter to battle bridge',
  () => {
    it(
      'does not treat battle-entry response as battle initialization',
      () => {
        const authority =
          encounter()

        const bridge =
          new ReconstructedLogresBattleEntryBridge(
            authority,
          )

        bridge.requestEntry()

        bridge.recordEntryResponse({
          rawCode:
            0,
        })

        expect(
          bridge.snapshot(),
        ).toMatchObject({
          phase:
            'entry-response-received',
          launch:
            null,
        })

        expect(
          authority.snapshot()
            .battleInitialized,
        ).toBe(
          false,
        )
      },
    )

    it(
      'creates battle scene launch only after authoritative battle initialization',
      () => {
        const authority =
          encounter()

        const bridge =
          new ReconstructedLogresBattleEntryBridge(
            authority,
          )

        bridge.requestEntry()

        const launch =
          bridge.recordBattleInitialized({
            battleSystemRef:
              'battle-system-1',
            battleKit: {
              weaponPanels: [
                {
                  unlocked:
                    true,
                  weaponRef:
                    'weapon-1',
                  normalSkillRef:
                    'normal-1',
                  specialSkillRef:
                    'special-1',
                  specialEpCost:
                    3,
                },
              ],
              selectedWeaponSlot:
                0,
              currentEp:
                4,
              epCap:
                10,
            },
          })

        expect(
          launch.sceneKey,
        ).toBe(
          LOGRES_BATTLE_SCENE_KEY,
        )

        expect(
          launch.sceneData,
        ).toMatchObject({
          selectedWeaponSlot:
            0,
          currentEp:
            4,
          epCap:
            10,
        })

        expect(
          launch.sceneData
            .weaponPanels,
        ).toHaveLength(
          5,
        )

        expect(
          authority.snapshot(),
        ).toMatchObject({
          battleInitialized:
            true,
          battleSystemRef:
            'battle-system-1',
        })

        expect(
          bridge.snapshot()
            .phase,
        ).toBe(
          'battle-ready',
        )
      },
    )

    it(
      'allows unresolved original identifiers without inventing them',
      () => {
        const authority =
          encounter()

        const bridge =
          new ReconstructedLogresBattleEntryBridge(
            authority,
          )

        expect(
          bridge.requestEntry(),
        ).toMatchObject({
          areaRef:
            null,
          symbolRef:
            null,
          mapPosition:
            null,
        })

        const launch =
          bridge.recordBattleInitialized({
            battleSystemRef:
              null,
            battleKit: {
              weaponPanels:
                [],
              selectedWeaponSlot:
                null,
              currentEp:
                0,
              epCap:
                null,
            },
          })

        expect(
          launch.battleSystemRef,
        ).toBeNull()
      },
    )

    it(
      'validates battle kit before mutating encounter initialization state',
      () => {
        const authority =
          encounter()

        const bridge =
          new ReconstructedLogresBattleEntryBridge(
            authority,
          )

        bridge.requestEntry()

        expect(
          () =>
            bridge.recordBattleInitialized({
              battleSystemRef:
                'battle-system-1',
              battleKit: {
                weaponPanels:
                  Array.from(
                    {
                      length:
                        6,
                    },
                    (_, index) => ({
                      unlocked:
                        true,
                      weaponRef:
                        `weapon-${index}`,
                      normalSkillRef:
                        `normal-${index}`,
                      specialSkillRef:
                        `special-${index}`,
                      specialEpCost:
                        1,
                    }),
                  ),
                selectedWeaponSlot:
                  0,
                currentEp:
                  0,
                epCap:
                  null,
              },
            }),
        ).toThrow(
          'at most five weapon slots',
        )

        expect(
          authority.snapshot()
            .battleInitialized,
        ).toBe(
          false,
        )

        expect(
          bridge.snapshot()
            .phase,
        ).toBe(
          'entry-requested',
        )
      },
    )

    it(
      'rejects initialization without a prior entry request',
      () => {
        const bridge =
          new ReconstructedLogresBattleEntryBridge(
            encounter(),
          )

        expect(
          () =>
            bridge.recordBattleInitialized({
              battleSystemRef:
                null,
              battleKit: {
                weaponPanels:
                  [],
                selectedWeaponSlot:
                  null,
                currentEp:
                  0,
                epCap:
                  null,
              },
            }),
        ).toThrow(
          'requires a prior entry request',
        )
      },
    )
  },
)
