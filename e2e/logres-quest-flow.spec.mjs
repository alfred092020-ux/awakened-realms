import {
  expect,
  test,
} from '@playwright/test'

test(
  'reconstructed quest flow stays authenticated, authoritative, and idempotent',
  async ({
    page,
  }) => {
    await page.goto(
      '/',
    )

    const result =
      await page.evaluate(
        async () => {
          const quest =
            await import(
              '/src/game/logres/server/LogresQuestInstanceAuthority.ts'
            )

          const authenticator =
            {
              actorRef:
                'player-1',
              sessionToken:
                'session-1',
            }

          const instance =
            quest.createReconstructedLogresQuestInstance(
              {
                instanceKey:
                  'e2e-quest-instance',
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
              },
            )

          const issued =
            quest.createReconstructedLogresQuestFlowState(
              {
                instance,
                authenticator,
                originalQuestUid:
                  null,
              },
            )

          const accepted =
            quest.applyReconstructedLogresQuestAccept(
              issued,
              {
                requestId:
                  'accept-1',
                authenticator,
              },
            )

          const progressed =
            quest.applyReconstructedLogresQuestProgress(
              accepted.state,
              {
                requestId:
                  'progress-1',
                progressKey:
                  'objective-1',
                authenticator,
              },
            )

          const completed =
            quest.applyReconstructedLogresQuestCompletion(
              progressed.state,
              {
                requestId:
                  'complete-1',
                authenticator,
                originalCompletionRef:
                  null,
              },
            )

          const rewarded =
            quest.applyReconstructedLogresQuestRewardGrant(
              completed.state,
              {
                grantKey:
                  'grant-1',
                authenticator,
                originalRewardRef:
                  null,
              },
            )

          const rewardRetry =
            quest.applyReconstructedLogresQuestRewardGrant(
              rewarded.state,
              {
                grantKey:
                  'grant-1',
                authenticator,
                originalRewardRef:
                  'different-retry-payload',
              },
            )

          let unauthorizedMessage =
            ''

          try {
            quest.applyReconstructedLogresQuestAccept(
              issued,
              {
                requestId:
                  'bad-accept',
                authenticator: {
                  actorRef:
                    'player-2',
                  sessionToken:
                    'session-1',
                },
              },
            )
          } catch (error) {
            unauthorizedMessage =
              error instanceof Error
                ? error.message
                : String(
                    error,
                  )
          }

          return {
            accepted:
              accepted.state.phase,
            progressed:
              progressed.state.phase,
            completed:
              completed.state.phase,
            rewarded:
              rewarded.state.phase,
            rewardRetryApplied:
              rewardRetry.applied,
            revision:
              rewarded.state.revision,
            originalQuestUid:
              rewarded.state.originalQuestUid,
            originalCompletionRef:
              rewarded.state.originalCompletionRef,
            originalRewardRef:
              rewarded.state.originalRewardRef,
            unauthorizedMessage,
          }
        },
      )

    expect(
      result,
    ).toEqual({
      accepted:
        'accepted',
      progressed:
        'in-progress',
      completed:
        'completed',
      rewarded:
        'reward-granted',
      rewardRetryApplied:
        false,
      revision:
        4,
      originalQuestUid:
        null,
      originalCompletionRef:
        null,
      originalRewardRef:
        null,
      unauthorizedMessage:
        'Quest flow mutation rejected for unauthenticated actor/session pair',
    })
  },
)
