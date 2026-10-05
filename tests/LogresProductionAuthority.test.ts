import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  openLogresServerAuthSession,
  revokeLogresServerAuthSession,
} from '../src/game/logres/server/LogresAuthSession'

import type {
  LogresTokenVerifier,
} from '../src/game/logres/server/LogresAuthSession'

import {
  assignLogresRole,
  createLogresModerationState,
  issueLogresSanction,
} from '../src/game/logres/server/LogresModerationAuthority'

import {
  applyLogresMutationIntent,
  applyLogresServerInternalMutation,
  createLogresProductionAuthority,
} from '../src/game/logres/server/LogresProductionAuthority'

const clock = (
  now: number,
) => ({
  nowSeconds: () =>
    now,
})

const verifier = (
  uid: string,
): LogresTokenVerifier => ({
  verifyToken: () => ({
    uid,
    provider:
      'google',
    email: null,
    displayName:
      null,
    disabled:
      false,
    tokenIssuedAtSeconds:
      0,
    tokenExpiresAtSeconds:
      10000,
  }),
})

const sessionFor = (
  uid: string,
) =>
  openLogresServerAuthSession(
    verifier(uid),
    {
      provider:
        'google',
      idToken: 't',
    },
    clock(1000),
    `sess-${uid}`,
    3600,
  )

const moderation = () => {
  let state =
    createLogresModerationState(
      ['admin-1'],
    )
  state =
    assignLogresRole(
      state,
      'admin-1',
      'mod-1',
      'moderator',
      100,
    )
  return state
}

describe(
  'Logres production authority',
  () => {
    it(
      'applies each authoritative mutation kind from a valid session',
      () => {
        let authority =
          createLogresProductionAuthority()
        const mod =
          moderation()
        const session =
          sessionFor('u1')

        const kinds = [
          [
            'battle-outcome',
            {
              victory:
                true,
            },
          ],
          [
            'progression',
            {
              xp: 100,
            },
          ],
          [
            'currency',
            {
              amount: 50,
            },
          ],
          [
            'inventory',
            {
              item: 'sword',
            },
          ],
          [
            'reward',
            {
              grant: 'g1',
            },
          ],
          [
            'summon',
            {
              sku: 'banner-1',
            },
          ],
          [
            'purchase',
            {
              sku: 'gem-pack',
            },
          ],
        ] as const

        kinds.forEach(
          (
            [kind, payload],
            i,
          ) => {
            const r =
              applyLogresMutationIntent(
                authority,
                mod,
                session,
                clock(2000),
                {
                  intentKey: `k${i}`,
                  kind,
                  payload,
                },
              )
            expect(
              r.applied,
            ).toBe(true)
            if (r.applied) {
              authority =
                r.state
            }
          },
        )

        expect(
          authority.appliedMutations,
        ).toHaveLength(7)
        expect(
          authority.appliedMutations.map(
            (m) => m.kind,
          ),
        ).toEqual([
          'battle-outcome',
          'progression',
          'currency',
          'inventory',
          'reward',
          'summon',
          'purchase',
        ])
      },
    )

    it(
      'binds mutation identity to the session uid, not the intent',
      () => {
        const authority =
          createLogresProductionAuthority()
        const r =
          applyLogresMutationIntent(
            authority,
            moderation(),
            sessionFor('real-uid'),
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 5,
                uid: 'forged-uid',
              },
            },
          )

        expect(
          r.applied,
        ).toBe(true)
        if (r.applied) {
          expect(
            r.mutation.uid,
          ).toBe('real-uid')
          expect(
            r.mutation.mutationKey,
          ).toBe(
            'real-uid:k1',
          )
        }
      },
    )

    it(
      'is idempotent: replayed uid+intentKey is a no-op',
      () => {
        let authority =
          createLogresProductionAuthority()
        const session =
          sessionFor('u1')
        const mod =
          moderation()

        const first =
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 5,
              },
            },
          )
        expect(
          first.applied,
        ).toBe(true)
        if (first.applied) {
          authority =
            first.state
        }

        const replay =
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2001),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 999,
              },
            },
          )

        expect(
          replay,
        ).toEqual({
          applied: false,
          reason:
            'duplicate-intent',
        })
        expect(
          authority.appliedMutations,
        ).toHaveLength(1)
      },
    )

    it(
      'scopes idempotency per uid so different players cannot collide',
      () => {
        let authority =
          createLogresProductionAuthority()
        const mod =
          moderation()

        for (const uid of [
          'u1',
          'u2',
        ]) {
          const r =
            applyLogresMutationIntent(
              authority,
              mod,
              sessionFor(uid),
              clock(2000),
              {
                intentKey:
                  'same-key',
                kind:
                  'currency',
                payload: {
                  amount: 1,
                },
              },
            )
          expect(
            r.applied,
          ).toBe(true)
          if (r.applied) {
            authority =
              r.state
          }
        }

        expect(
          authority.appliedMutations,
        ).toHaveLength(2)
      },
    )

    it(
      'fails closed on a revoked or expired session',
      () => {
        const authority =
          createLogresProductionAuthority()
        const mod =
          moderation()

        const revoked =
          revokeLogresServerAuthSession(
            sessionFor('u1'),
          )

        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            revoked,
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 1,
              },
            },
          ),
        ).toThrow(
          /expired or revoked/,
        )
      },
    )

    it(
      'fails closed on a banned subject',
      () => {
        const authority =
          createLogresProductionAuthority()
        let mod =
          moderation()
        mod =
          issueLogresSanction(
            mod,
            'mod-1',
            {
              sanctionKey:
                'b1',
              subjectUid:
                'u1',
              kind: 'ban',
              reason:
                'cheating',
              expiresAtSeconds:
                null,
            },
            1500,
          )

        const result =
          applyLogresMutationIntent(
            authority,
            mod,
            sessionFor('u1'),
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 1,
              },
            },
          )

        expect(
          result,
        ).toEqual({
          applied: false,
          reason:
            'banned',
        })
      },
    )

    it(
      'rejects unknown kinds and malformed payloads',
      () => {
        const authority =
          createLogresProductionAuthority()
        const mod =
          moderation()
        const session =
          sessionFor('u1')

        // Unknown kind
        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'god-mode' as never,
              payload: {},
            },
          ),
        ).toThrow(
          /not a known authoritative kind/,
        )

        // battle-outcome without boolean victory
        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k2',
              kind:
                'battle-outcome',
              payload: {
                victory:
                  'yes',
              },
            },
          ),
        ).toThrow(
          /boolean victory/,
        )

        // currency with a non-integer amount
        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k3',
              kind:
                'currency',
              payload: {
                amount: 1.5,
              },
            },
          ),
        ).toThrow(
          /safe-integer amount/,
        )

        // summon without sku
        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k4',
              kind:
                'summon',
              payload: {},
            },
          ),
        ).toThrow(
          /non-empty sku/,
        )
      },
    )

    it(
      'blocks a client-originated leaderboard write but allows a server-internal one',
      () => {
        let authority =
          createLogresProductionAuthority()
        const mod =
          moderation()
        const session =
          sessionFor('u1')

        expect(() =>
          applyLogresMutationIntent(
            authority,
            mod,
            session,
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'leaderboard-write',
              payload: {
                board:
                  'season-elo',
                delta: 9999,
              },
            },
          ),
        ).toThrow(
          /server-internal only/,
        )

        const internal =
          applyLogresServerInternalMutation(
            authority,
            'u1',
            'leaderboard-write',
            'battle-42',
            {
              board:
                'season-elo',
              delta: 25,
            },
            2000,
          )

        expect(
          internal.applied,
        ).toBe(true)
        if (
          internal.applied
        ) {
          authority =
            internal.state
          expect(
            authority
              .appliedMutations[0]
              ?.mutationKey,
          ).toBe(
            'u1:internal:battle-42',
          )
        }
      },
    )

    it(
      'rejects forged provenance',
      () => {
        const authority =
          createLogresProductionAuthority()

        const forged = {
          ...authority,
          provenance:
            'FORGED',
        }

        expect(() =>
          applyLogresMutationIntent(
            forged as never,
            moderation(),
            sessionFor('u1'),
            clock(2000),
            {
              intentKey: 'k1',
              kind:
                'currency',
              payload: {
                amount: 1,
              },
            },
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )
  },
)
