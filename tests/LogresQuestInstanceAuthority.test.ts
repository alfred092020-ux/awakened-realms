import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createReconstructedLogresQuestInstance,
  createUnresolvedTutorialQuestInstance,
  LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
} from '../src/game/logres/server/LogresQuestInstanceAuthority'

describe(
  'reconstructed Logres quest-instance authority',
  () => {
    it(
      'keeps every unresolved opening-tutorial historical value empty',
      () => {
        const instance =
          createUnresolvedTutorialQuestInstance()

        expect(
          instance,
        ).toEqual({
          provenance:
            'RECONSTRUCTED',
          instanceKey:
            'opening-tutorial',
          questRecordId:
            null,
          mapId:
            null,
          roomId:
            null,
          playerSpawn:
            null,
          objectiveIds:
            [],
          encounterIds:
            [],
          npcStateIds:
            [],
          tutorialOverlayIds:
            [],
          rules: {
            timeLimitSeconds:
              null,
            defeatLimit:
              null,
            battleCapacity:
              null,
            requiredPower:
              null,
          },
        })

        expect(
          instance.provenance,
        ).toBe(
          LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
        )
      },
    )

    it(
      'keeps static map identity separate from room, spawn, encounters, overlays, and rules',
      () => {
        const instance =
          createReconstructedLogresQuestInstance({
            instanceKey:
              'test-instance',
            questRecordId:
              'test-quest-record',
            mapId:
              '002_000_00003',
            roomId:
              'room-1',
            playerSpawn: {
              col: 4,
              row: 9,
            },
            objectiveIds: [
              'objective-a',
            ],
            encounterIds: [
              'encounter-a',
            ],
            npcStateIds: [
              'npc-state-a',
            ],
            tutorialOverlayIds: [
              'overlay-a',
            ],
            rules: {
              timeLimitSeconds:
                600,
              defeatLimit:
                2,
              battleCapacity:
                5,
              requiredPower:
                100,
            },
          })

        expect(
          instance.mapId,
        ).toBe(
          '002_000_00003',
        )
        expect(
          instance.roomId,
        ).toBe(
          'room-1',
        )
        expect(
          instance.playerSpawn,
        ).toEqual({
          col: 4,
          row: 9,
        })
        expect(
          instance.encounterIds,
        ).toEqual([
          'encounter-a',
        ])
        expect(
          instance.tutorialOverlayIds,
        ).toEqual([
          'overlay-a',
        ])
        expect(
          instance.rules,
        ).toEqual({
          timeLimitSeconds:
            600,
          defeatLimit:
            2,
          battleCapacity:
            5,
          requiredPower:
            100,
        })
      },
    )

    it(
      'does not permit malformed map ids or guessed numeric defaults',
      () => {
        expect(
          () =>
            createReconstructedLogresQuestInstance({
              instanceKey:
                'bad-map',
              questRecordId:
                null,
              mapId:
                'Millennium-Tree',
              roomId:
                null,
              playerSpawn:
                null,
              objectiveIds:
                [],
              encounterIds:
                [],
              npcStateIds:
                [],
              tutorialOverlayIds:
                [],
              rules: {
                timeLimitSeconds:
                  null,
                defeatLimit:
                  null,
                battleCapacity:
                  null,
                requiredPower:
                  null,
              },
            }),
        ).toThrow(
          'Quest mapId must be null or a canonical',
        )

        expect(
          () =>
            createReconstructedLogresQuestInstance({
              instanceKey:
                'bad-capacity',
              questRecordId:
                null,
              mapId:
                null,
              roomId:
                null,
              playerSpawn:
                null,
              objectiveIds:
                [],
              encounterIds:
                [],
              npcStateIds:
                [],
              tutorialOverlayIds:
                [],
              rules: {
                timeLimitSeconds:
                  null,
                defeatLimit:
                  null,
                battleCapacity:
                  0,
                requiredPower:
                  null,
              },
            }),
        ).toThrow(
          'Quest battleCapacity must be null or a positive safe integer',
        )
      },
    )

    it(
      'copies and freezes instance collections at the authority boundary',
      () => {
        const objectives = [
          'objective-a',
        ]

        const instance =
          createReconstructedLogresQuestInstance({
            instanceKey:
              'immutable-test',
            questRecordId:
              null,
            mapId:
              null,
            roomId:
              null,
            playerSpawn:
              null,
            objectiveIds:
              objectives,
            encounterIds:
              [],
            npcStateIds:
              [],
            tutorialOverlayIds:
              [],
            rules: {
              timeLimitSeconds:
                null,
              defeatLimit:
                null,
              battleCapacity:
                null,
              requiredPower:
                null,
            },
          })

        objectives.push(
          'objective-b',
        )

        expect(
          instance.objectiveIds,
        ).toEqual([
          'objective-a',
        ])

        expect(
          Object.isFrozen(
            instance,
          ),
        ).toBe(
          true,
        )
        expect(
          Object.isFrozen(
            instance.objectiveIds,
          ),
        ).toBe(
          true,
        )
        expect(
          Object.isFrozen(
            instance.rules,
          ),
        ).toBe(
          true,
        )
      },
    )
  },
)
