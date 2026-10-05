import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  activateLogresShard,
  createInitialLogresServerTopology,
  deactivateLogresShard,
  LOGRES_MIN_ACTIVE_SHARDS,
  resolveLogresSessionShard,
} from '../src/game/logres/server/LogresServerTopology'

import type {
  LogresShardConfig,
} from '../src/game/logres/server/LogresServerTopology'

const shard = (
  id: string,
): LogresShardConfig => ({
  shardId: id,
  label: `Shard ${id}`,
  sessionCapacity: 100,
  region: 'us-east',
})

const three = (): [
  LogresShardConfig,
  LogresShardConfig,
  LogresShardConfig,
] => [
  shard('s1'),
  shard('s2'),
  shard('s3'),
]

describe(
  'Logres server topology',
  () => {
    it(
      'starts with exactly three active shards',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        expect(
          topology.activeShards,
        ).toHaveLength(
          LOGRES_MIN_ACTIVE_SHARDS,
        )
        expect(
          topology.activeShards.map(
            (s) => s.shardId,
          ),
        ).toEqual([
          's1',
          's2',
          's3',
        ])
        expect(
          topology.minActiveShards,
        ).toBe(3)
      },
    )

    it(
      'activates an arbitrary future shard without client rebuild',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        const next =
          activateLogresShard(
            topology,
            shard('s4'),
          )

        expect(
          next.activeShards,
        ).toHaveLength(4)
        expect(
          next.activeShards[3]
            ?.shardId,
        ).toBe('s4')
        expect(
          next.revision,
        ).toBe(1)
        // Original is unchanged.
        expect(
          topology.activeShards,
        ).toHaveLength(3)
      },
    )

    it(
      'rejects activating a duplicate shard id',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        expect(() =>
          activateLogresShard(
            topology,
            shard('s1'),
          ),
        ).toThrow(
          /already active/,
        )
      },
    )

    it(
      'refuses to deactivate below the three-shard floor',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        expect(() =>
          deactivateLogresShard(
            topology,
            's3',
          ),
        ).toThrow(
          /minimum active shard/,
        )
      },
    )

    it(
      'deactivates an extra shard once above the floor',
      () => {
        const topology =
          activateLogresShard(
            createInitialLogresServerTopology(
              three(),
            ),
            shard('s4'),
          )

        const reduced =
          deactivateLogresShard(
            topology,
            's4',
          )

        expect(
          reduced.activeShards.map(
            (s) => s.shardId,
          ),
        ).toEqual([
          's1',
          's2',
          's3',
        ])
      },
    )

    it(
      'fails closed resolving an unknown shard id',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        expect(() =>
          resolveLogresSessionShard(
            topology,
            's99',
          ),
        ).toThrow(
          /not active/,
        )

        expect(
          resolveLogresSessionShard(
            topology,
            's2',
          ).shardId,
        ).toBe('s2')
      },
    )

    it(
      'rejects invalid shard configs',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        for (const bad of [
          {
            ...shard('x'),
            shardId: '',
          },
          {
            ...shard('x'),
            sessionCapacity: 0,
          },
          {
            ...shard('x'),
            sessionCapacity: -5,
          },
          {
            ...shard('x'),
            region: '',
          },
        ]) {
          expect(() =>
            activateLogresShard(
              topology,
              bad,
            ),
          ).toThrow()
        }
      },
    )

    it(
      'rejects forged provenance',
      () => {
        const topology =
          createInitialLogresServerTopology(
            three(),
          )

        const forged = {
          ...topology,
          provenance:
            'FORGED',
        }

        expect(() =>
          activateLogresShard(
            forged as never,
            shard('s4'),
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )
  },
)
