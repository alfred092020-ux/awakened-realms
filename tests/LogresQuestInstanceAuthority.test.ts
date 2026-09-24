import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  applyReconstructedLogresQuestAccept,
  applyReconstructedLogresQuestCompletion,
  applyReconstructedLogresQuestProgress,
  applyReconstructedLogresQuestRewardGrant,
  createReconstructedLogresQuestFlowState,
  createReconstructedLogresQuestInstance,
  createUnresolvedTutorialQuestInstance,
  LOGRES_RECONSTRUCTED_QUEST_INSTANCE_PROVENANCE,
} from '../src/game/logres/server/LogresQuestInstanceAuthority'

function createQuestInstanceForFlow() {
  return createReconstructedLogresQuestInstance({
    instanceKey:
      'flow-instance',
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
}

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

    it(
      'keeps accept/progress/completion/reward transitions server-authoritative and idempotent',
      () => {
        const authenticator = {
          actorRef:
            'player-1',
          sessionToken:
            'session-1',
        }

        const issued =
          createReconstructedLogresQuestFlowState({
            instance:
              createQuestInstanceForFlow(),
            authenticator,
            originalQuestUid:
              null,
          })

        const accepted =
          applyReconstructedLogresQuestAccept(
            issued,
            {
              requestId:
                'accept-req-1',
              authenticator,
            },
          )

        expect(
          accepted.applied,
        ).toBe(
          true,
        )
        expect(
          accepted.state.phase,
        ).toBe(
          'accepted',
        )

        const acceptRetry =
          applyReconstructedLogresQuestAccept(
            accepted.state,
            {
              requestId:
                'accept-req-1',
              authenticator,
            },
          )

        expect(
          acceptRetry.applied,
        ).toBe(
          false,
        )
        expect(
          acceptRetry.state,
        ).toBe(
          accepted.state,
        )

        const progressed =
          applyReconstructedLogresQuestProgress(
            accepted.state,
            {
              requestId:
                'progress-req-1',
              progressKey:
                'kill-1-slime',
              authenticator,
            },
          )

        expect(
          progressed.applied,
        ).toBe(
          true,
        )
        expect(
          progressed.state.phase,
        ).toBe(
          'in-progress',
        )
        expect(
          progressed.state.progressKeys,
        ).toEqual([
          'kill-1-slime',
        ])

        const progressRetry =
          applyReconstructedLogresQuestProgress(
            progressed.state,
            {
              requestId:
                'progress-req-1',
              progressKey:
                'kill-1-slime',
              authenticator,
            },
          )

        expect(
          progressRetry.applied,
        ).toBe(
          false,
        )
        expect(
          progressRetry.state,
        ).toBe(
          progressed.state,
        )

        const completed =
          applyReconstructedLogresQuestCompletion(
            progressed.state,
            {
              requestId:
                'complete-req-1',
              authenticator,
              originalCompletionRef:
                null,
            },
          )

        expect(
          completed.applied,
        ).toBe(
          true,
        )
        expect(
          completed.state.phase,
        ).toBe(
          'completed',
        )
        expect(
          completed.state.originalCompletionRef,
        ).toBeNull()

        const completeRetry =
          applyReconstructedLogresQuestCompletion(
            completed.state,
            {
              requestId:
                'complete-req-1',
              authenticator,
              originalCompletionRef:
                'ignored-on-retry',
            },
          )

        expect(
          completeRetry.applied,
        ).toBe(
          false,
        )
        expect(
          completeRetry.state,
        ).toBe(
          completed.state,
        )

        const rewarded =
          applyReconstructedLogresQuestRewardGrant(
            completed.state,
            {
              grantKey:
                'grant-1',
              authenticator,
              originalRewardRef:
                null,
            },
          )

        expect(
          rewarded.applied,
        ).toBe(
          true,
        )
        expect(
          rewarded.state.phase,
        ).toBe(
          'reward-granted',
        )
        expect(
          rewarded.state.originalRewardRef,
        ).toBeNull()

        const rewardRetry =
          applyReconstructedLogresQuestRewardGrant(
            rewarded.state,
            {
              grantKey:
                'grant-1',
              authenticator,
              originalRewardRef:
                'ignored-on-retry',
            },
          )

        expect(
          rewardRetry.applied,
        ).toBe(
          false,
        )
        expect(
          rewardRetry.state,
        ).toBe(
          rewarded.state,
        )
      },
    )

    it(
      'requires authenticated actor/session ownership for persistence mutations',
      () => {
        const state =
          createReconstructedLogresQuestFlowState({
            instance:
              createQuestInstanceForFlow(),
            authenticator: {
              actorRef:
                'player-1',
              sessionToken:
                'session-1',
            },
            originalQuestUid:
              null,
          })

        expect(
          () =>
            applyReconstructedLogresQuestAccept(
              state,
              {
                requestId:
                  'accept-1',
                authenticator: {
                  actorRef:
                    'player-2',
                  sessionToken:
                    'session-1',
                },
              },
            ),
        ).toThrow(
          'unauthenticated actor/session pair',
        )
      },
    )

    it(
      'keeps unresolved historical quest identifiers nullable in persisted flow state',
      () => {
        const flow =
          createReconstructedLogresQuestFlowState({
            instance:
              createQuestInstanceForFlow(),
            authenticator: {
              actorRef:
                'player-1',
              sessionToken:
                'session-1',
            },
            originalQuestUid:
              null,
          })

        expect(
          flow.originalQuestUid,
        ).toBeNull()
        expect(
          flow.originalCompletionRef,
        ).toBeNull()
        expect(
          flow.originalRewardRef,
        ).toBeNull()
      },
    )
  },
)
