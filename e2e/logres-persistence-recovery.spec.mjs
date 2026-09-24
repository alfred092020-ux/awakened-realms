import {
  execFileSync,
} from 'node:child_process'
import {
  expect,
  test,
} from '@playwright/test'

test(
  'replacement-server recovery survives reconnect without duplicating quest rewards or inventory grants',
  async () => {
    const script = String.raw`
import {
  applyReconstructedLogresInventoryGrant,
  createReconstructedLogresInventory,
} from './src/game/logres/server/LogresInventoryAuthority.ts'
import {
  createReconstructedLogresQuestInstance,
} from './src/game/logres/server/LogresQuestInstanceAuthority.ts'
import {
  InMemoryLogresPersistenceBackingStore,
  LogresPersistenceRecovery,
} from './src/game/logres/server/LogresPersistenceRecovery.ts'
import {
  LogresQuestAuthority,
} from './src/game/logres/systems/LogresQuestRuntime.ts'

const accountId = 'e2e-persistence-account'
const backing = new InMemoryLogresPersistenceBackingStore()
const first = new LogresPersistenceRecovery(backing)
const session = {
  accountId,
  sessionId: 'before-reconnect',
  authenticated: true,
}

first.saveProgression(
  accountId,
  {
    provenance: 'RECONSTRUCTED',
    revision: 2,
    jobKey: 'novice',
    level: 2,
    experience: 25,
    appliedCommandIds: ['progression-command-1'],
  },
  'progression-command-1',
)

const quest = createReconstructedLogresQuestInstance({
  instanceKey: 'recovery-quest',
  questRecordId: null,
  mapId: '002_000_00001',
  roomId: null,
  playerSpawn: null,
  objectiveIds: ['objective-1'],
  encounterIds: [],
  npcStateIds: [],
  tutorialOverlayIds: [],
  rules: {
    timeLimitSeconds: null,
    defeatLimit: null,
    battleCapacity: null,
    requiredPower: null,
  },
})

const questAuthority = new LogresQuestAuthority(
  first.createQuestPersistence(accountId),
)
questAuthority.accept(session, quest, 'accept-1')
questAuthority.progress(
  session,
  quest.instanceKey,
  'objective-1',
  3,
  'progress-1',
)
questAuthority.complete(session, quest.instanceKey, 'complete-1')
questAuthority.grantReward(
  session,
  quest.instanceKey,
  {
    rewardKey: 'reward-1',
    originalItemId: null,
    quantity: 1,
    currencyAmount: null,
  },
  'reward-command-1',
)

const granted = applyReconstructedLogresInventoryGrant(
  createReconstructedLogresInventory(),
  {
    grantKey: 'inventory-grant-1',
    entries: [{
      itemKey: 'reward-line-1',
      originalItemId: null,
      quantity: 1,
    }],
  },
)
first.saveInventory(
  accountId,
  granted.state,
  'inventory-grant-1',
)
first.saveSession(
  accountId,
  {
    provenance: 'RECONSTRUCTED',
    revision: 4,
    characterKey: 'character-1',
    scene: 'field',
    mapId: '002_000_00001',
  },
  'session-field-1',
)

const reloaded = new LogresPersistenceRecovery(backing)
const afterReconnectSession = {
  ...session,
  sessionId: 'after-reconnect',
}
const retryQuest = new LogresQuestAuthority(
  reloaded.createQuestPersistence(accountId),
)
const rewardRetry = retryQuest.grantReward(
  afterReconnectSession,
  quest.instanceKey,
  {
    rewardKey: 'reward-1',
    originalItemId: null,
    quantity: 1,
    currencyAmount: null,
  },
  'reward-command-1',
)

const restoredBeforeInventoryRetry = reloaded.recover(accountId)
const inventoryRetry = applyReconstructedLogresInventoryGrant(
  restoredBeforeInventoryRetry.inventory,
  {
    grantKey: 'inventory-grant-1',
    entries: [{
      itemKey: 'reward-line-1',
      originalItemId: null,
      quantity: 1,
    }],
  },
)
const beforeCheckpointRevision = restoredBeforeInventoryRetry.revision
const afterCheckpointRetry = reloaded.saveInventory(
  accountId,
  inventoryRetry.state,
  'inventory-grant-1',
)
const restoredQuest = retryQuest.read(
  afterReconnectSession,
  quest.instanceKey,
)

console.log(JSON.stringify({
  progression: afterCheckpointRetry.progression,
  session: afterCheckpointRetry.session,
  quest: restoredQuest,
  questRewardRetryRevision: rewardRetry.revision,
  inventory: afterCheckpointRetry.inventory,
  inventoryRetryApplied: inventoryRetry.applied,
  beforeCheckpointRevision,
  afterCheckpointRevision: afterCheckpointRetry.revision,
}))
`

    const output =
      execFileSync(
        './node_modules/.bin/tsx',
        [
          '-e',
          script,
        ],
        {
          cwd:
            process.cwd(),
          encoding:
            'utf8',
        },
      )
        .trim()
        .split('\n')
        .at(-1)

    if (!output) {
      throw new Error(
        'Persistence recovery E2E produced no snapshot.',
      )
    }

    const result =
      JSON.parse(output)

    expect(
      result.progression,
    ).toMatchObject({
      revision: 2,
      jobKey:
        'novice',
      level: 2,
      experience: 25,
    })
    expect(
      result.session,
    ).toMatchObject({
      revision: 4,
      characterKey:
        'character-1',
      scene:
        'field',
      mapId:
        '002_000_00001',
    })
    expect(
      result.quest.phase,
    ).toBe('REWARDED')
    expect(
      result.quest
        .progressByObjective[
          'objective-1'
        ],
    ).toBe(3)
    expect(
      result.quest
        .appliedCommandIds
        .filter(
          (id) =>
            id ===
            'reward-command-1',
        ),
    ).toHaveLength(1)
    expect(
      result.questRewardRetryRevision,
    ).toBe(
      result.quest.revision,
    )
    expect(
      result.inventoryRetryApplied,
    ).toBe(false)
    expect(
      result.inventory
        .appliedGrantKeys,
    ).toEqual([
      'inventory-grant-1',
    ])
    expect(
      result.inventory.entries,
    ).toHaveLength(1)
    expect(
      result.afterCheckpointRevision,
    ).toBe(
      result.beforeCheckpointRevision,
    )
  },
)
