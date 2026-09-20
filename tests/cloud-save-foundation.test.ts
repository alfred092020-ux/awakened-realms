import {
  beforeEach,
  describe,
  expect,
  it,
} from 'vitest'

import {
  MetaSaveSystem,
} from '../src/game/meta/MetaSaveSystem'

import {
  MetaSession,
} from '../src/game/meta/MetaSession'

import {
  createDefaultMetaState,
} from '../src/game/meta/MetaProgression'

describe(
  'Cloud save foundation',
  () => {
    beforeEach(() => {
      localStorage.clear()
    })

    it(
      'tracks when local progress was updated',
      () => {
        const saves =
          new MetaSaveSystem()

        const state =
          createDefaultMetaState(
            1000,
          )

        saves.save(
          state,
          4321,
        )

        expect(
          saves.getUpdatedAt(),
        ).toBe(4321)
      },
    )

    it(
      'clears save sync metadata',
      () => {
        const saves =
          new MetaSaveSystem()

        saves.save(
          createDefaultMetaState(),
          9000,
        )

        saves.clear()

        expect(
          saves.getUpdatedAt(),
        ).toBe(0)

        expect(
          localStorage.getItem(
            'awakened-realms.meta.v1',
          ),
        ).toBeNull()
      },
    )

    it(
      'can replace local progress with a cloud state',
      () => {
        const session =
          new MetaSession()

        const cloudState =
          createDefaultMetaState(
            5000,
          )

        cloudState.essence =
          123

        cloudState.bestWave =
          42

        cloudState.upgrades[
          'attack-training'
        ] = 7

        session.replaceState(
          cloudState,
          7000,
        )

        const loaded =
          session.getState()

        expect(
          loaded.essence,
        ).toBe(123)

        expect(
          loaded.bestWave,
        ).toBe(42)

        expect(
          loaded.upgrades[
            'attack-training'
          ],
        ).toBe(7)

        expect(
          session.getUpdatedAt(),
        ).toBe(7000)
      },
    )
  },
)
