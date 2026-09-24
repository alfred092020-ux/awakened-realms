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

import {
  InMemoryLogresQuestPersistence,
  LOGRES_QUEST_RUNTIME_EVIDENCE,
  LogresQuestAuthority,
} from '../src/game/logres/systems/LogresQuestRuntime'

describe(
  'reconstructed Logres quest gameplay authority',
  () => {
    const session = {
      accountId:
        'account-faker',
      sessionId:
        'session-1',
      authenticated:
        true,
    } as const

    const makeInstance = () =>
      createReconstructedLogresQuestInstance({
        instanceKey:
          'quest-test',
        questRecordId:
          null,
        mapId:
          '002_000_00001',
        roomId:
          null,
        playerSpawn:
          null,
        objectiveIds: [
          'defeat-target',
        ],
        encounterIds: [],
        npcStateIds: [],
        tutorialOverlayIds: [],
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

    it(
      'follows server-authored accept, progress, result and reward phases',
      () => {
        const store =
          new InMemoryLogresQuestPersistence()
        const authority =
          new LogresQuestAuthority(
            store,
          )

        const accepted =
          authority.accept(
            session,
            makeInstance(),
            'accept-1',
          )
        expect(
          accepted.phase,
        ).toBe(
          'IN_PROGRESS',
        )
        expect(
          accepted.progressByObjective,
        ).toEqual({
          'defeat-target': 0,
        })

        const progressed =
          authority.progress(
            session,
            'quest-test',
            'defeat-target',
            1,
            'progress-1',
          )
        expect(
          progressed
            .progressByObjective[
              'defeat-target'
            ],
        ).toBe(1)

        const completed =
          authority.complete(
            session,
            'quest-test',
            'complete-1',
          )
        expect(
          completed.phase,
        ).toBe(
          'COMPLETED',
        )

        const rewarded =
          authority.grantReward(
            session,
            'quest-test',
            {
              rewardKey:
                'reconstruction-reward',
              originalItemId:
                null,
              quantity:
                null,
              currencyAmount:
                null,
            },
            'reward-1',
          )
        expect(
          rewarded.phase,
        ).toBe(
          'REWARDED',
        )
        expect(
          rewarded.reward,
        ).toEqual({
          rewardKey:
            'reconstruction-reward',
          originalItemId:
            null,
          quantity:
            null,
          currencyAmount:
            null,
        })
      },
    )

    it(
      'is idempotent for repeated command ids',
      () => {
        const store =
          new InMemoryLogresQuestPersistence()
        const authority =
          new LogresQuestAuthority(
            store,
          )

        const first =
          authority.accept(
            session,
            makeInstance(),
            'accept-idempotent',
          )
        const duplicate =
          authority.accept(
            session,
            makeInstance(),
            'accept-idempotent',
          )
        expect(
          duplicate,
        ).toEqual(first)

        const progress =
          authority.progress(
            session,
            'quest-test',
            'defeat-target',
            3,
            'progress-idempotent',
          )
        const repeated =
          authority.progress(
            session,
            'quest-test',
            'defeat-target',
            3,
            'progress-idempotent',
          )
        expect(
          repeated,
        ).toEqual(progress)
        expect(
          repeated
            .progressByObjective[
              'defeat-target'
            ],
        ).toBe(3)
      },
    )

    it(
      'persists by authenticated account across authority instances',
      () => {
        const store =
          new InMemoryLogresQuestPersistence()
        const first =
          new LogresQuestAuthority(
            store,
          )
        first.accept(
          session,
          makeInstance(),
          'accept-persist',
        )
        first.progress(
          session,
          'quest-test',
          'defeat-target',
          2,
          'progress-persist',
        )

        const restored =
          new LogresQuestAuthority(
            store,
          ).read(
            session,
            'quest-test',
          )

        expect(
          restored?.phase,
        ).toBe(
          'IN_PROGRESS',
        )
        expect(
          restored
            ?.progressByObjective[
              'defeat-target'
            ],
        ).toBe(2)
      },
    )

    it(
      'rejects unauthenticated mutations and unknown objectives',
      () => {
        const store =
          new InMemoryLogresQuestPersistence()
        const authority =
          new LogresQuestAuthority(
            store,
          )

        expect(
          () =>
            authority.accept(
              {
                ...session,
                authenticated:
                  false,
              },
              makeInstance(),
              'accept-noauth',
            ),
        ).toThrow(
          'authenticated session',
        )

        authority.accept(
          session,
          makeInstance(),
          'accept-auth',
        )

        expect(
          () =>
            authority.progress(
              session,
              'quest-test',
              'invented-objective',
              1,
              'bad-progress',
            ),
        ).toThrow(
          'not part of this instance',
        )
      },
    )

    it(
      'keeps recovered state sequencing separate from unresolved historical payloads',
      () => {
        expect(
          LOGRES_QUEST_RUNTIME_EVIDENCE
            .serverStatePushSequence,
        ).toContain(
          'S_GMCL_QUEST_INFO_STATE_PROGRESS_UPDATE',
        )
        expect(
          LOGRES_QUEST_RUNTIME_EVIDENCE
            .serverStatePushSequence,
        ).toContain(
          'S_GMCL_QUEST_INFO_STATE_RESULT',
        )
        expect(
          LOGRES_QUEST_RUNTIME_EVIDENCE
            .unresolvedHistoricalPayloads
            .join(' '),
        ).toContain(
          'historical quest source payload corpus',
        )
      },
    )
  },
)
