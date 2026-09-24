import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  applyReconstructedLogresInventoryGrant,
  createReconstructedLogresInventory,
} from '../src/game/logres/server/LogresInventoryAuthority'
import {
  createReconstructedLogresQuestInstance,
} from '../src/game/logres/server/LogresQuestInstanceAuthority'
import {
  InMemoryLogresPersistenceBackingStore,
  LogresPersistenceRecovery,
} from '../src/game/logres/server/LogresPersistenceRecovery'
import {
  LogresQuestAuthority,
} from '../src/game/logres/systems/LogresQuestRuntime'

const accountId =
  'persistence-account'

const session = {
  accountId,
  sessionId:
    'session-before-reconnect',
  authenticated:
    true,
}

function createQuest() {
  return createReconstructedLogresQuestInstance({
    instanceKey:
      'persistence-quest',
    questRecordId:
      null,
    mapId:
      '002_000_00001',
    roomId:
      null,
    playerSpawn:
      null,
    objectiveIds: [
      'objective-1',
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
}

describe(
  'Logres persistence recovery',
  () => {
    it(
      'recovers progression, quest, inventory and session state across service recreation',
      () => {
        const backing =
          new InMemoryLogresPersistenceBackingStore()
        const first =
          new LogresPersistenceRecovery(
            backing,
          )

        first.saveProgression(
          accountId,
          {
            provenance:
              'RECONSTRUCTED',
            revision: 3,
            jobKey:
              'novice',
            level: 2,
            experience: 25,
            appliedCommandIds: [
              'progression-1',
            ],
          },
          'progression-1',
        )

        const questAuthority =
          new LogresQuestAuthority(
            first.createQuestPersistence(
              accountId,
            ),
          )
        const quest =
          createQuest()

        questAuthority.accept(
          session,
          quest,
          'quest-accept-1',
        )
        questAuthority.progress(
          session,
          quest.instanceKey,
          'objective-1',
          4,
          'quest-progress-1',
        )
        questAuthority.complete(
          session,
          quest.instanceKey,
          'quest-complete-1',
        )
        questAuthority.grantReward(
          session,
          quest.instanceKey,
          {
            rewardKey:
              'quest-reward-1',
            originalItemId:
              null,
            quantity:
              1,
            currencyAmount:
              null,
          },
          'quest-reward-command-1',
        )

        const inventoryGrant =
          applyReconstructedLogresInventoryGrant(
            createReconstructedLogresInventory(),
            {
              grantKey:
                'battle-grant-1',
              entries: [
                {
                  itemKey:
                    'battle-reward-line-1',
                  originalItemId:
                    null,
                  quantity: 2,
                },
              ],
            },
          )

        first.saveInventory(
          accountId,
          inventoryGrant.state,
          'inventory-battle-grant-1',
        )
        first.saveSession(
          accountId,
          {
            provenance:
              'RECONSTRUCTED',
            revision: 5,
            characterKey:
              'character-1',
            scene:
              'field',
            mapId:
              '002_000_00001',
          },
          'session-field-1',
        )

        const reloaded =
          new LogresPersistenceRecovery(
            backing,
          )
        const restored =
          reloaded.recover<{
            provenance: string
            revision: number
            jobKey: string
            level: number
            experience: number
            appliedCommandIds:
              string[]
          }, {
            provenance: string
            revision: number
            characterKey: string
            scene: string
            mapId: string
          }>(
            accountId,
          )

        expect(restored)
          .not.toBeNull()
        expect(
          restored?.progression,
        ).toMatchObject({
          revision: 3,
          jobKey:
            'novice',
          level: 2,
          experience: 25,
        })
        expect(
          restored?.inventory,
        ).toEqual(
          inventoryGrant.state,
        )
        expect(
          restored?.session,
        ).toMatchObject({
          revision: 5,
          characterKey:
            'character-1',
          scene:
            'field',
          mapId:
            '002_000_00001',
        })

        const restoredQuest =
          new LogresQuestAuthority(
            reloaded
              .createQuestPersistence(
                accountId,
              ),
          ).read(
            {
              ...session,
              sessionId:
                'session-after-reconnect',
            },
            quest.instanceKey,
          )

        expect(
          restoredQuest?.phase,
        ).toBe(
          'REWARDED',
        )
        expect(
          restoredQuest
            ?.progressByObjective[
              'objective-1'
            ],
        ).toBe(4)
        expect(
          restoredQuest
            ?.appliedCommandIds,
        ).toEqual([
          'quest-accept-1',
          'quest-progress-1',
          'quest-complete-1',
          'quest-reward-command-1',
        ])
      },
    )

    it(
      'keeps reconnect retries idempotent and rejects state rollback',
      () => {
        const backing =
          new InMemoryLogresPersistenceBackingStore()
        const first =
          new LogresPersistenceRecovery(
            backing,
          )
        const quest =
          createQuest()
        const authority =
          new LogresQuestAuthority(
            first.createQuestPersistence(
              accountId,
            ),
          )

        authority.accept(
          session,
          quest,
          'accept-1',
        )
        authority.complete(
          session,
          quest.instanceKey,
          'complete-1',
        )
        const rewarded =
          authority.grantReward(
            session,
            quest.instanceKey,
            {
              rewardKey:
                'reward-1',
              originalItemId:
                null,
              quantity:
                1,
              currencyAmount:
                null,
            },
            'reward-command-1',
          )

        const inventory =
          applyReconstructedLogresInventoryGrant(
            createReconstructedLogresInventory(),
            {
              grantKey:
                'grant-1',
              entries: [
                {
                  itemKey:
                    'line-1',
                  originalItemId:
                    null,
                  quantity: 1,
                },
              ],
            },
          ).state

        const stored =
          first.saveInventory(
            accountId,
            inventory,
            'inventory-grant-1',
          )

        const reloaded =
          new LogresPersistenceRecovery(
            backing,
          )
        const retryAuthority =
          new LogresQuestAuthority(
            reloaded
              .createQuestPersistence(
                accountId,
              ),
          )
        const rewardRetry =
          retryAuthority.grantReward(
            {
              ...session,
              sessionId:
                'reconnected',
            },
            quest.instanceKey,
            {
              rewardKey:
                'reward-1',
              originalItemId:
                null,
              quantity:
                1,
              currencyAmount:
                null,
            },
            'reward-command-1',
          )

        expect(
          rewardRetry.revision,
        ).toBe(
          rewarded.revision,
        )
        expect(
          rewardRetry
            .appliedCommandIds
            .filter(
              (id) =>
                id ===
                'reward-command-1',
            ),
        ).toHaveLength(1)

        const inventoryRetry =
          applyReconstructedLogresInventoryGrant(
            reloaded
              .recover(accountId)!
              .inventory,
            {
              grantKey:
                'grant-1',
              entries: [
                {
                  itemKey:
                    'line-1',
                  originalItemId:
                    null,
                  quantity: 1,
                },
              ],
            },
          )

        expect(
          inventoryRetry.applied,
        ).toBe(false)

        const checkpointRetry =
          reloaded.saveInventory(
            accountId,
            inventoryRetry.state,
            'inventory-grant-1',
          )

        expect(
          checkpointRetry.revision,
        ).toBe(
          stored.revision,
        )
        expect(
          checkpointRetry
            .inventory
            .appliedGrantKeys,
        ).toEqual([
          'grant-1',
        ])

        expect(
          () =>
            reloaded.saveInventory(
              accountId,
              createReconstructedLogresInventory(),
              'inventory-stale-write',
            ),
        ).toThrow(
          'inventory revision cannot move backwards',
        )
      },
    )

    it(
      'fails closed on corrupt serialized state instead of returning partial recovery',
      () => {
        const backing = {
          value:
            null as string | null,
          read: () =>
            backing.value,
          write: (
            _accountId: string,
            serialized: string,
          ) => {
            backing.value =
              serialized
          },
        }
        const recovery =
          new LogresPersistenceRecovery(
            backing,
          )

        recovery.saveProgression(
          accountId,
          {
            revision: 1,
            level: 1,
          },
          'progression-1',
        )

        backing.value =
          backing.value!
            .replace(
              '"schemaVersion":1',
              '"schemaVersion":999',
            )

        expect(
          () =>
            recovery.recover(
              accountId,
            ),
        ).toThrow(
          'schema version is unsupported',
        )
      },
    )
  },
)
