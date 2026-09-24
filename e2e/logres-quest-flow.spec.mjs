import {
  execFileSync,
} from 'node:child_process'
import {
  expect,
  test,
} from '@playwright/test'

test(
  'authenticated quest authority persists accept -> progress -> complete -> reward idempotently',
  async () => {
    const script = String.raw`
import { createReconstructedLogresQuestInstance } from './src/game/logres/server/LogresQuestInstanceAuthority.ts'
import { InMemoryLogresQuestPersistence, LogresQuestAuthority } from './src/game/logres/systems/LogresQuestRuntime.ts'

const session = {
  accountId: 'e2e-account',
  sessionId: 'e2e-session',
  authenticated: true,
}

const store = new InMemoryLogresQuestPersistence()
const authority = new LogresQuestAuthority(store)
const instance = createReconstructedLogresQuestInstance({
  instanceKey: 'e2e-quest',
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

authority.accept(session, instance, 'accept-1')
authority.progress(session, 'e2e-quest', 'objective-1', 4, 'progress-1')
authority.progress(session, 'e2e-quest', 'objective-1', 4, 'progress-1')
authority.complete(session, 'e2e-quest', 'complete-1')
authority.grantReward(
  session,
  'e2e-quest',
  {
    rewardKey: 'e2e-reward',
    originalItemId: null,
    quantity: null,
    currencyAmount: null,
  },
  'reward-1',
)

const restored = new LogresQuestAuthority(store).read(session, 'e2e-quest')
console.log(JSON.stringify(restored))
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
        'Quest E2E produced no authority snapshot.',
      )
    }

    const restored =
      JSON.parse(output)

    expect(
      restored.phase,
    ).toBe('REWARDED')
    expect(
      restored
        .progressByObjective[
          'objective-1'
        ],
    ).toBe(4)
    expect(
      restored.reward,
    ).toEqual({
      rewardKey:
        'e2e-reward',
      originalItemId:
        null,
      quantity:
        null,
      currencyAmount:
        null,
    })
    expect(
      restored
        .appliedCommandIds,
    ).toEqual([
      'accept-1',
      'progress-1',
      'complete-1',
      'reward-1',
    ])
  },
)
