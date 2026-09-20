import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  buildPublicProfile,
  calculateProfilePower,
} from '../src/game/social/LeaderboardService'

import {
  createDefaultMetaState,
} from '../src/game/meta/MetaProgression'

describe(
  'Leaderboard profiles',
  () => {
    it(
      'calculates public player power',
      () => {
        const state =
          createDefaultMetaState()

        state.upgrades[
          'attack-training'
        ] = 4

        state.upgrades[
          'vitality-training'
        ] = 3

        state.upgrades[
          'haste-training'
        ] = 2

        expect(
          calculateProfilePower(
            state,
          ),
        ).toBe(
          144,
        )
      },
    )

    it(
      'creates a safe public profile without private account data',
      () => {
        const state =
          createDefaultMetaState()

        state.bestWave =
          27

        state.lifetimeRuns =
          12

        const profile =
          buildPublicProfile(
            'user-123',
            'Realm Hero',
            state,
            9000,
          )

        expect(
          profile,
        ).toEqual({
          uid:
            'user-123',

          displayName:
            'Realm Hero',

          bestWave:
            27,

          lifetimeRuns:
            12,

          power:
            100,

          updatedAt:
            9000,
        })

        expect(
          'email' in profile,
        ).toBe(false)
      },
    )

    it(
      'limits overly long public names',
      () => {
        const state =
          createDefaultMetaState()

        const profile =
          buildPublicProfile(
            'user-1',
            'A'.repeat(
              100,
            ),
            state,
            1,
          )

        expect(
          profile.displayName,
        ).toHaveLength(
          40,
        )
      },
    )
  },
)
