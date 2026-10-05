import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  applyLogresLeaderboardWrite,
  createLogresLeaderboard,
  readLogresLeaderboard,
} from '../src/game/logres/server/LogresLeaderboardAuthority'

describe(
  'Logres leaderboard authority',
  () => {
    it(
      'creates an empty board',
      () => {
        const board =
          createLogresLeaderboard(
            'season-elo',
          )

        expect(
          board.provenance,
        ).toBe(
          'RECONSTRUCTED',
        )
        expect(
          readLogresLeaderboard(
            board,
          ),
        ).toEqual([])
      },
    )

    it(
      'rejects an unknown board id',
      () => {
        expect(() =>
          createLogresLeaderboard(
            'not-a-board' as never,
          ),
        ).toThrow(
          /not a known board/,
        )
      },
    )

    it(
      'applies a server score write and ranks by score',
      () => {
        let board =
          createLogresLeaderboard(
            'season-elo',
          )

        board =
          applyLogresLeaderboardWrite(
            board,
            {
              eventKey:
                'e1',
              uid: 'u-low',
              delta: 10,
            },
          ).state

        board =
          applyLogresLeaderboardWrite(
            board,
            {
              eventKey:
                'e2',
              uid: 'u-high',
              delta: 50,
            },
          ).state

        const ranked =
          readLogresLeaderboard(
            board,
          )

        expect(
          ranked.map(
            (e) => e.uid,
          ),
        ).toEqual([
          'u-high',
          'u-low',
        ])
        expect(
          ranked[0]?.score,
        ).toBe(50)
      },
    )

    it(
      'treats a replayed event key as an idempotent no-op',
      () => {
        let board =
          createLogresLeaderboard(
            'quest-clears',
          )

        board =
          applyLogresLeaderboardWrite(
            board,
            {
              eventKey:
                'battle-1',
              uid: 'u1',
              delta: 1,
            },
          ).state

        const replay =
          applyLogresLeaderboardWrite(
            board,
            {
              eventKey:
                'battle-1',
              uid: 'u1',
              delta: 1,
            },
          )

        expect(
          replay.applied,
        ).toBe(false)
        expect(
          replay.state,
        ).toBe(board)
        expect(
          readLogresLeaderboard(
            board,
          )[0]?.score,
        ).toBe(1)
      },
    )

    it(
      'accumulates distinct events for the same uid',
      () => {
        let board =
          createLogresLeaderboard(
            'summon-points',
          )

        for (const key of [
          'e1',
          'e2',
          'e3',
        ]) {
          board =
            applyLogresLeaderboardWrite(
              board,
              {
                eventKey:
                  key,
                uid: 'u1',
                delta: 3,
              },
            ).state
        }

        expect(
          readLogresLeaderboard(
            board,
          )[0]?.score,
        ).toBe(9)
      },
    )

    it(
      'rejects non-finite deltas and empty keys',
      () => {
        const board =
          createLogresLeaderboard(
            'season-elo',
          )

        for (const bad of [
          {
            eventKey: '',
            uid: 'u1',
            delta: 1,
          },
          {
            eventKey:
              'e1',
            uid: '',
            delta: 1,
          },
          {
            eventKey:
              'e1',
            uid: 'u1',
            delta:
              Number.NaN,
          },
          {
            eventKey:
              'e1',
            uid: 'u1',
            delta:
              Number.POSITIVE_INFINITY,
          },
        ]) {
          expect(() =>
            applyLogresLeaderboardWrite(
              board,
              bad,
            ),
          ).toThrow()
        }
      },
    )

    it(
      'rejects forged provenance',
      () => {
        const board =
          createLogresLeaderboard(
            'season-elo',
          )

        const forged = {
          ...board,
          provenance:
            'FORGED',
        }

        expect(() =>
          applyLogresLeaderboardWrite(
            forged as never,
            {
              eventKey:
                'e1',
              uid: 'u1',
              delta: 1,
            },
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )
  },
)
