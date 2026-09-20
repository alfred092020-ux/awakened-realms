import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createEnemyForWave,
  RunEngine,
} from '../src/game/roguelike/RunEngine'

import {
  simulateRun,
} from '../src/game/roguelike/RunSimulator'

import {
  SeededRandom,
} from '../src/game/roguelike/SeededRandom'

describe(
  'Idle roguelike core',
  () => {
    it(
      'produces repeatable seeded randomness',
      () => {
        const first =
          new SeededRandom(
            123456,
          )

        const second =
          new SeededRandom(
            123456,
          )

        const firstValues =
          Array.from(
            { length: 10 },
            () =>
              first.next(),
          )

        const secondValues =
          Array.from(
            { length: 10 },
            () =>
              second.next(),
          )

        expect(
          firstValues,
        ).toEqual(
          secondValues,
        )
      },
    )

    it(
      'creates a boss every tenth wave',
      () => {
        expect(
          createEnemyForWave(
            9,
          ).boss,
        ).toBe(false)

        expect(
          createEnemyForWave(
            10,
          ).boss,
        ).toBe(true)

        expect(
          createEnemyForWave(
            20,
          ).boss,
        ).toBe(true)
      },
    )

    it(
      'scales later enemies above early enemies',
      () => {
        const early =
          createEnemyForWave(
            1,
          )

        const later =
          createEnemyForWave(
            15,
          )

        expect(
          later.maxHp,
        ).toBeGreaterThan(
          early.maxHp,
        )

        expect(
          later.attack,
        ).toBeGreaterThan(
          early.attack,
        )

        expect(
          later.goldReward,
        ).toBeGreaterThan(
          early.goldReward,
        )
      },
    )

    it(
      'automatically fights without player input',
      () => {
        const engine =
          new RunEngine(
            777,
          )

        const before =
          engine.getSnapshot()

        engine.advance(
          5000,
        )

        const after =
          engine.getSnapshot()

        expect(
          after.elapsedMs,
        ).toBeGreaterThan(
          before.elapsedMs,
        )

        expect(
          after.kills > 0 ||
          after.player.hp <
            before.player.hp ||
          after.status !==
            'running',
        ).toBe(true)
      },
    )

    it(
      'offers three unique upgrades on level up',
      () => {
        const engine =
          new RunEngine(
            8128,
          )

        let guard = 0

        while (
          engine
            .getSnapshot()
            .status ===
          'running'
        ) {
          engine.advance(
            250,
          )

          guard += 1

          if (guard > 5000) {
            throw new Error(
              'Upgrade test did not reach a decision.',
            )
          }
        }

        const snapshot =
          engine.getSnapshot()

        expect(
          snapshot.status,
        ).toBe('upgrade')

        expect(
          snapshot
            .pendingUpgrades,
        ).toHaveLength(3)

        const ids =
          snapshot
            .pendingUpgrades
            .map(
              (upgrade) =>
                upgrade.id,
            )

        expect(
          new Set(ids).size,
        ).toBe(3)
      },
    )

    it(
      'applies a selected upgrade',
      () => {
        const engine =
          new RunEngine(
            8128,
          )

        while (
          engine
            .getSnapshot()
            .status ===
          'running'
        ) {
          engine.advance(
            250,
          )
        }

        const before =
          engine.getSnapshot()

        const power =
          before
            .pendingUpgrades
            .find(
              (upgrade) =>
                upgrade.id ===
                'power-surge',
            )

        if (power) {
          engine.chooseUpgrade(
            power.id,
          )

          expect(
            engine
              .getSnapshot()
              .player.attack,
          ).toBeGreaterThan(
            before.player
              .attack,
          )

          return
        }

        const selected =
          before
            .pendingUpgrades[0]

        if (!selected) {
          throw new Error(
            'Missing upgrade choice.',
          )
        }

        engine.chooseUpgrade(
          selected.id,
        )

        expect(
          engine
            .getSnapshot()
            .status,
        ).toBe('running')
      },
    )

    it(
      'replays the same run identically with the same seed and choices',
      () => {
        const first =
          simulateRun(
            424242,
          )

        const second =
          simulateRun(
            424242,
          )

        expect(
          second,
        ).toEqual(
          first,
        )
      },
    )

    it(
      'can simulate a complete run without Phaser or manual input',
      () => {
        const simulation =
          simulateRun(
            987654,
          )

        expect(
          simulation
            .result.kills,
        ).toBeGreaterThan(0)

        expect(
          simulation
            .result.elapsedMs,
        ).toBeGreaterThan(0)

        expect(
          simulation
            .result.waveReached,
        ).toBeGreaterThanOrEqual(
          1,
        )

        expect(
          typeof simulation
            .result.won,
        ).toBe('boolean')
      },
    )
  },
)
