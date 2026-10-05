import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  assignLogresRole,
  createLogresModerationState,
  issueLogresSanction,
} from '../src/game/logres/server/LogresModerationAuthority'

import {
  createLogresWorldChatState,
  readLogresWorldChatLog,
  submitLogresWorldChatIntent,
} from '../src/game/logres/server/LogresWorldChatAuthority'

const makeModeration =
  () => {
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
  'Logres world-chat authority',
  () => {
    it(
      'accepts a valid message and stamps it server-side',
      () => {
        const chat =
          createLogresWorldChatState(
            's1',
          )

        const result =
          submitLogresWorldChatIntent(
            chat,
            makeModeration(),
            'uid-1',
            {
              body:
                'hello world',
            },
            1000,
          )

        expect(
          result.accepted,
        ).toBe(true)
        if (
          result.accepted
        ) {
          expect(
            result.message,
          ).toMatchObject({
            sequence: 1,
            senderUid:
              'uid-1',
            body:
              'hello world',
            sentAtSeconds:
              1000,
            shardId:
              's1',
          })
        }
      },
    )

    it(
      'rejects empty, oversized, and malformed intents',
      () => {
        const chat =
          createLogresWorldChatState(
            's1',
          )
        const mod =
          makeModeration()

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u1',
            {
              body: '   ',
            },
            1000,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'empty-body',
        })

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u1',
            {
              body: 'x'.repeat(
                401,
              ),
            },
            1000,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'too-long',
        })

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u1',
            null as never,
            1000,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'invalid-intent',
        })
      },
    )

    it(
      'enforces the per-sender rate limit',
      () => {
        let chat =
          createLogresWorldChatState(
            's1',
          )
        const mod =
          makeModeration()

        const first =
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u1',
            {
              body: 'one',
            },
            1000,
          )
        expect(
          first.accepted,
        ).toBe(true)
        if (
          first.accepted
        ) {
          chat =
            first.state
        }

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u1',
            {
              body: 'two',
            },
            1001,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'rate-limited',
        })

        // A different sender is unaffected.
        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'u2',
            {
              body: 'hi',
            },
            1001,
          ).accepted,
        ).toBe(true)
      },
    )

    it(
      'rejects messages from muted and banned subjects',
      () => {
        const chat =
          createLogresWorldChatState(
            's1',
          )
        let mod =
          makeModeration()

        mod =
          issueLogresSanction(
            mod,
            'mod-1',
            {
              sanctionKey:
                'mute1',
              subjectUid:
                'muted-u',
              kind:
                'mute',
              reason:
                'spam',
              expiresAtSeconds:
                null,
            },
            500,
          )
        mod =
          issueLogresSanction(
            mod,
            'mod-1',
            {
              sanctionKey:
                'ban1',
              subjectUid:
                'banned-u',
              kind:
                'ban',
              reason:
                'cheat',
              expiresAtSeconds:
                null,
            },
            500,
          )

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'muted-u',
            {
              body: 'hi',
            },
            1000,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'muted',
        })

        expect(
          submitLogresWorldChatIntent(
            chat,
            mod,
            'banned-u',
            {
              body: 'hi',
            },
            1000,
          ),
        ).toEqual({
          accepted:
            false,
          reason:
            'banned',
        })
      },
    )

    it(
      'ignores any sender identity the client puts in the intent',
      () => {
        const chat =
          createLogresWorldChatState(
            's1',
          )

        const result =
          submitLogresWorldChatIntent(
            chat,
            makeModeration(),
            'real-uid',
            {
              body: 'hi',
              senderUid:
                'forged-uid',
            } as never,
            1000,
          )

        expect(
          result.accepted,
        ).toBe(true)
        if (
          result.accepted
        ) {
          expect(
            result.message
              .senderUid,
          ).toBe('real-uid')
        }
      },
    )

    it(
      'assigns increasing server sequence numbers',
      () => {
        let chat =
          createLogresWorldChatState(
            's1',
          )
        const mod =
          makeModeration()

        for (const [i, body] of [
          'a',
          'b',
          'c',
        ].entries()) {
          const r =
            submitLogresWorldChatIntent(
              chat,
              mod,
              `u${i}`,
              {
                body,
              },
              1000 + i,
            )
          expect(
            r.accepted,
          ).toBe(true)
          if (r.accepted) {
            chat =
              r.state
          }
        }

        const log =
          readLogresWorldChatLog(
            chat,
          )
        expect(
          log.map(
            (m) =>
              m.sequence,
          ),
        ).toEqual([
          1, 2, 3,
        ])
        expect(
          Object.isFrozen(
            log,
          ),
        ).toBe(true)
      },
    )

    it(
      'rejects forged provenance',
      () => {
        const chat =
          createLogresWorldChatState(
            's1',
          )

        const forged = {
          ...chat,
          provenance:
            'FORGED',
        }

        expect(() =>
          submitLogresWorldChatIntent(
            forged as never,
            makeModeration(),
            'u1',
            {
              body: 'hi',
            },
            1000,
          ),
        ).toThrow(
          /provenance/,
        )
      },
    )
  },
)
