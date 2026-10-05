import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  evaluateLogresServerAuthSession,
  openLogresServerAuthSession,
  requireActiveLogresServerAuthSession,
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

const goodIdentity =
  (
    overrides:
      Partial<LogresVerifiedIdentity> = {},
  ): LogresVerifiedIdentity => ({
  uid: 'uid-1',
  provider:
    'google',
  email:
    'a@b.c',
  displayName:
    'Player',
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
    identity: LogresVerifiedIdentity,
  ): LogresTokenVerifier => ({
  verifyToken: () =>
    identity,
})

describe(
  'Logres server auth session boundary',
  () => {
    it(
      'opens a session from a verified identity and binds uid server-side',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity(),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          )

        expect(
          session.provenance,
        ).toBe(
          'RECONSTRUCTED',
        )
        expect(
          session.identity.uid,
        ).toBe(
          'uid-1',
        )
        expect(
          session.revoked,
        ).toBe(false)
        expect(
          Object.isFrozen(
            session,
          ),
        ).toBe(true)
      },
    )

    it(
      'caps session expiry at the earlier of token expiry and max lifetime',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                tokenExpiresAtSeconds: 800,
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          )

        // token expiry 800 < now 500 + lifetime 3600
        expect(
          session.expiresAtSeconds,
        ).toBe(800)
      },
    )

    it(
      'rejects an expired token',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                tokenExpiresAtSeconds: 400,
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /expired/,
        )
      },
    )

    it(
      'rejects a not-yet-valid token',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                tokenIssuedAtSeconds: 600,
                tokenExpiresAtSeconds: 1000,
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /not yet valid/,
        )
      },
    )

    it(
      'rejects a disabled account',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                disabled: true,
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /disabled/,
        )
      },
    )

    it(
      'rejects a provider mismatch between presented credential and verified identity',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'password',
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /provider does not match/,
        )
      },
    )

    it(
      'rejects malformed presented credentials',
      () => {
        for (const bad of [
          {
            provider:
              'google',
            idToken: '',
          },
          {
            provider:
              'evil',
            idToken:
              'token',
          },
        ]) {
          expect(() =>
            openLogresServerAuthSession(
              verifierFor(
                goodIdentity(),
              ),
              bad as never,
              clock(500),
              'session-1',
              3600,
            ),
          ).toThrow()
        }
      },
    )

    it(
      'marks an expired session revoked on evaluation and blocks requireActive',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                tokenExpiresAtSeconds: 600,
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          )

        const evaluated =
          evaluateLogresServerAuthSession(
            session,
            clock(700),
          )

        expect(
          evaluated.revoked,
        ).toBe(true)

        expect(() =>
          requireActiveLogresServerAuthSession(
            session,
            clock(700),
          ),
        ).toThrow(
          /expired or revoked/,
        )
      },
    )

    it(
      'revokes a session immutably',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'password',
              }),
            ),
            {
              provider:
                'password',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          )

        const revoked =
          revokeLogresServerAuthSession(
            session,
          )

        expect(
          revoked.revoked,
        ).toBe(true)
        expect(
          Object.isFrozen(
            revoked,
          ),
        ).toBe(true)

        expect(() =>
          requireActiveLogresServerAuthSession(
            revoked,
            clock(500),
          ),
        ).toThrow()
      },
    )

    it(
      'rejects tampered session provenance',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity(),
            ),
            {
              provider:
                'google',
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          )

        const forged = {
          ...session,
          provenance:
            'FORGED',
        }

        expect(() =>
          evaluateLogresServerAuthSession(
            forged as never,
            clock(500),
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )

    it(
      'opens a guest session from a verified anonymous identity',
      () => {
        const session =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'guest',
                email:
                  null,
                displayName:
                  null,
              }),
            ),
            {
              provider:
                'guest',
              idToken:
                'anon-token',
            },
            clock(500),
            'guest-session-1',
            3600,
          )

        expect(
          session.identity.provider,
        ).toBe(
          'guest',
        )
        expect(
          session.identity.uid,
        ).toBe(
          'uid-1',
        )
        expect(
          session.revoked,
        ).toBe(false)
      },
    )

    it(
      'distinguishes guest sessions from google/password sessions',
      () => {
        const guest =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'guest',
                uid:
                  'anon-uid',
                email:
                  null,
              }),
            ),
            {
              provider:
                'guest',
              idToken:
                'anon-token',
            },
            clock(500),
            's-guest',
            3600,
          )

        const google =
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'google',
                uid:
                  'google-uid',
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'google-token',
            },
            clock(500),
            's-google',
            3600,
          )

        expect(
          guest.identity.provider,
        ).toBe(
          'guest',
        )
        expect(
          google.identity.provider,
        ).toBe(
          'google',
        )
        expect(
          guest.identity.uid,
        ).not.toBe(
          google.identity.uid,
        )
      },
    )

    it(
      'rejects a guest token relabeled as a permanent provider',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'guest',
              }),
            ),
            {
              provider:
                'google',
              idToken:
                'anon-token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /provider does not match/,
        )
      },
    )

    it(
      'rejects a permanent token relabeled as guest',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity({
                provider:
                  'google',
              }),
            ),
            {
              provider:
                'guest',
              idToken:
                'google-token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /provider does not match/,
        )
      },
    )

    it(
      'rejects an unknown provider on the presented credential',
      () => {
        expect(() =>
          openLogresServerAuthSession(
            verifierFor(
              goodIdentity(),
            ),
            {
              provider:
                'anonymous' as never,
              idToken:
                'token',
            },
            clock(500),
            'session-1',
            3600,
          ),
        ).toThrow(
          /provider/,
        )
      },
    )
  },
)
