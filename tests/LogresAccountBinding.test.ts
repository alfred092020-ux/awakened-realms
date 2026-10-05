import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  bindLogresGuestAccount,
  createLogresAccountBindingState,
  registerLogresGuestAccount,
  resolveLogresAccountForSession,
} from '../src/game/logres/server/LogresAccountBinding'

import {
  openLogresServerAuthSession,
  revokeLogresServerAuthSession,
} from '../src/game/logres/server/LogresAuthSession'

import type {
  LogresTokenVerifier,
  LogresVerifiedIdentity,
} from '../src/game/logres/server/LogresAuthSession'

const clock = (
  now: number,
) => ({
  nowSeconds: () =>
    now,
})

const identity =
  (
    overrides:
      Partial<LogresVerifiedIdentity> = {},
  ): LogresVerifiedIdentity => ({
  uid: 'uid-x',
  provider:
    'guest',
  email:
    null,
  displayName:
    null,
  disabled:
    false,
  tokenIssuedAtSeconds:
    100,
  tokenExpiresAtSeconds:
    1000,
  ...overrides,
})

const verifierFor =
  (
    result:
      | LogresVerifiedIdentity
      | ((credential: {
          provider: string
          idToken: string
        }) => LogresVerifiedIdentity),
  ): LogresTokenVerifier => ({
  verifyToken:
    typeof result === 'function'
      ? result
      : () => result,
})

const guestSession = (
  uid = 'guest-uid-1',
) =>
  openLogresServerAuthSession(
    verifierFor(
      identity({
        provider:
          'guest',
        uid,
      }),
    ),
    {
      provider:
        'guest',
      idToken:
        'anon-token',
    },
    clock(500),
    `session-${uid}`,
    3600,
  )

const boundIdentity = (
  provider: 'google' | 'password',
  uid = 'subject-uid-1',
): LogresVerifiedIdentity =>
  identity({
    provider,
    uid,
    email:
      'p@x.y',
  })

const stateWithGuest = (
  guestUid = 'guest-uid-1',
  accountId = 'acct-1',
) =>
  registerLogresGuestAccount(
    createLogresAccountBindingState(),
    guestSession(guestUid),
    clock(500),
    accountId,
  )

describe(
  'Logres account binding contract',
  () => {
    it(
      'registers a guest account keyed by a server account id',
      () => {
        const state =
          stateWithGuest()

        const account =
          state.accounts[
            'acct-1'
          ]

        expect(
          account.guest,
        ).toBe(true)
        expect(
          account.guestUid,
        ).toBe(
          'guest-uid-1',
        )
        expect(
          account.boundSubject,
        ).toBeNull()
        // The server account id — not the Firebase uid — keys the record.
        expect(
          account.accountId,
        ).toBe(
          'acct-1',
        )
      },
    )

    it(
      'rejects guest registration from a non-guest session',
      () => {
        const googleSession =
          openLogresServerAuthSession(
            verifierFor(
              identity({
                provider:
                  'google',
                uid:
                  'g-uid',
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'g-token',
            },
            clock(500),
            's-1',
            3600,
          )

        expect(() =>
          registerLogresGuestAccount(
            createLogresAccountBindingState(),
            googleSession,
            clock(500),
            'acct-1',
          ),
        ).toThrow(
          /guest session/,
        )
      },
    )

    it(
      'rejects guest registration with a revoked session',
      () => {
        const session =
          revokeLogresServerAuthSession(
            guestSession(),
          )

        expect(() =>
          registerLogresGuestAccount(
            createLogresAccountBindingState(),
            session,
            clock(500),
            'acct-1',
          ),
        ).toThrow(
          /expired or revoked/,
        )
      },
    )

    it(
      'binds a guest account to a verified google subject',
      () => {
        const state =
          stateWithGuest()

        const result =
          bindLogresGuestAccount(
            state,
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        expect(
          result.applied,
        ).toBe(true)
        expect(
          result.account.boundSubject,
        ).toEqual({
          provider:
            'google',
          subjectUid:
            'subject-uid-1',
          email:
            'p@x.y',
        })
        expect(
          result.state.subjectOwners[
            'google:subject-uid-1'
          ],
        ).toBe(
          'acct-1',
        )
        expect(
          result.state.bindings,
        ).toHaveLength(1)
        expect(
          result.binding.bindingKey,
        ).toBe(
          'acct-1:google:subject-uid-1',
        )
      },
    )

    it(
      'preserves the guest account id and guest uid across binding so progression survives',
      () => {
        const before =
          stateWithGuest()

        const guestRecord =
          before.accounts[
            'acct-1'
          ]

        const result =
          bindLogresGuestAccount(
            before,
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('password'),
            ),
            {
              provider:
                'password',
              idToken:
                'pw-token',
            },
          )

        // The durable identity is the server account id; the original
        // anonymous uid is retained as provenance. Progression keyed to
        // `acct-1` is untouched by binding.
        expect(
          result.account.accountId,
        ).toBe(
          guestRecord.accountId,
        )
        expect(
          result.account.guestUid,
        ).toBe(
          'guest-uid-1',
        )
        expect(
          result.account.guest,
        ).toBe(true)
      },
    )

    it(
      'resolves the same account for a post-binding permanent session',
      () => {
        const bound =
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        // After linking, the player presents a google session bearing the
        // now-linked uid; the server resolves it back to the same account.
        const resolved =
          resolveLogresAccountForSession(
            bound.state,
            identity({
              provider:
                'google',
              uid:
                'subject-uid-1',
            }),
          )

        expect(
          resolved?.accountId,
        ).toBe(
          'acct-1',
        )
      },
    )

    it(
      'is idempotent: replaying the same binding does not re-apply',
      () => {
        const first =
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        const replay =
          bindLogresGuestAccount(
            first.state,
            guestSession(),
            clock(700),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        expect(
          replay.applied,
        ).toBe(false)
        expect(
          replay.state.bindings,
        ).toHaveLength(1)
        expect(
          replay.state,
        ).toBe(
          first.state,
        )
      },
    )

    it(
      'rejects binding to a subject already owned by another account',
      () => {
        const bound =
          bindLogresGuestAccount(
            stateWithGuest('guest-a', 'acct-a'),
            guestSession('guest-a'),
            clock(600),
            verifierFor(
              boundIdentity('google', 'shared-subject'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        const secondState =
          registerLogresGuestAccount(
            bound.state,
            guestSession('guest-b'),
            clock(610),
            'acct-b',
          )

        // A second guest tries to claim the already-owned Google subject.
        expect(() =>
          bindLogresGuestAccount(
            secondState,
            guestSession('guest-b'),
            clock(620),
            verifierFor(
              boundIdentity('google', 'shared-subject'),
            ),
            {
              provider:
                'google',
              idToken:
                'stolen-token',
            },
          ),
        ).toThrow(
          /already bound to a different account/,
        )
      },
    )

    it(
      'rejects rebinding an already-bound account to a different subject',
      () => {
        const bound =
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google', 'subject-1'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        expect(() =>
          bindLogresGuestAccount(
            bound.state,
            guestSession(),
            clock(700),
            verifierFor(
              boundIdentity('google', 'subject-2'),
            ),
            {
              provider:
                'google',
              idToken:
                'other-token',
            },
          ),
        ).toThrow(
          /already bound to a different subject/,
        )
      },
    )

    it(
      'rejects rebinding an already-bound account to a different provider',
      () => {
        const bound =
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          )

        expect(() =>
          bindLogresGuestAccount(
            bound.state,
            guestSession(),
            clock(700),
            verifierFor(
              boundIdentity('password', 'pw-subject'),
            ),
            {
              provider:
                'password',
              idToken:
                'pw-token',
            },
          ),
        ).toThrow(
          /already bound to a different subject/,
        )
      },
    )

    it(
      'rejects binding from a non-guest session',
      () => {
        const googleSession =
          openLogresServerAuthSession(
            verifierFor(
              identity({
                provider:
                  'google',
                uid:
                  'g-uid',
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'g-token',
            },
            clock(500),
            's-1',
            3600,
          )

        expect(() =>
          bindLogresGuestAccount(
            stateWithGuest(),
            googleSession,
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          ),
        ).toThrow(
          /Only a guest session/,
        )
      },
    )

    it(
      'rejects binding with no registered guest account for the verified uid',
      () => {
        expect(() =>
          bindLogresGuestAccount(
            // Account exists for a different guest uid.
            stateWithGuest('other-guest', 'acct-1'),
            guestSession('guest-uid-1'),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          ),
        ).toThrow(
          /No guest account/,
        )
      },
    )

    it(
      'rejects a mismatched provider between presented binding and verified identity',
      () => {
        expect(() =>
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            // Verifier decodes a password token while the client claims google.
            verifierFor(
              boundIdentity('password'),
            ),
            {
              provider:
                'google',
              idToken:
                'relabeled-token',
            },
          ),
        ).toThrow(
          /does not match presented provider/,
        )
      },
    )

    it(
      'rejects a guest binding target provider',
      () => {
        expect(() =>
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            verifierFor(
              identity({
                provider:
                  'guest',
                uid:
                  'anon-2',
              }),
            ),
            {
              provider:
                'guest' as never,
              idToken:
                'anon-token-2',
            },
          ),
        ).toThrow(
          /Bind target provider/,
        )
      },
    )

    it(
      'rejects tampered binding state provenance',
      () => {
        const forged = {
          ...stateWithGuest(),
          provenance:
            'FORGED',
        }

        expect(() =>
          bindLogresGuestAccount(
            forged as never,
            guestSession(),
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )

    it(
      'rejects an expired or revoked guest session at bind time',
      () => {
        const revoked =
          revokeLogresServerAuthSession(
            guestSession(),
          )

        expect(() =>
          bindLogresGuestAccount(
            stateWithGuest(),
            revoked,
            clock(600),
            verifierFor(
              boundIdentity('google'),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
          ),
        ).toThrow(
          /expired or revoked/,
        )
      },
    )

    it(
      'does not trust a client-asserted uid; only the verifier-derived subject is bound',
      () => {
        let capturedProvider:
          string | null =
          null

        const spyVerifier:
          LogresTokenVerifier = {
          verifyToken: (credential) => {
            capturedProvider =
              credential.provider

            // The verifier's uid is authoritative; any uid the client
            // attached to the request is ignored entirely.
            return boundIdentity(
              'google',
              'verified-subject',
            )
          },
        }

        const result =
          bindLogresGuestAccount(
            stateWithGuest(),
            guestSession(),
            clock(600),
            spyVerifier,
            {
              provider:
                'google',
              idToken:
                'token',
            },
          )

        expect(
          capturedProvider,
        ).toBe(
          'google',
        )
        expect(
          result.account.boundSubject
            ?.subjectUid,
        ).toBe(
          'verified-subject',
        )
      },
    )

    it(
      'leaves state untouched when the verifier throws',
      () => {
        const state =
          stateWithGuest()

        const throwingVerifier:
          LogresTokenVerifier = {
          verifyToken: () => {
            throw new Error(
              'bad token',
            )
          },
        }

        expect(() =>
          bindLogresGuestAccount(
            state,
            guestSession(),
            clock(600),
            throwingVerifier,
            {
              provider:
                'google',
              idToken:
                'bad-token',
            },
          ),
        ).toThrow(
          'bad token',
        )

        // Atomicity: failed binding produces no record, no owner, no event.
        expect(
          state.bindings,
        ).toHaveLength(0)
        expect(
          Object.keys(
            state.subjectOwners,
          ),
        ).toHaveLength(0)
        expect(
          state.accounts[
            'acct-1'
          ].boundSubject,
        ).toBeNull()
      },
    )
  },
)
