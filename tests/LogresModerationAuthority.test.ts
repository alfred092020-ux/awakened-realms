import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  assignLogresRole,
  createLogresModerationState,
  getActiveLogresSanction,
  issueLogresSanction,
  readLogresAuditLog,
} from '../src/game/logres/server/LogresModerationAuthority'

describe(
  'Logres moderation authority',
  () => {
    it(
      'seeds admins and keeps an empty append-only audit log',
      () => {
        const state =
          createLogresModerationState(
            ['admin-1'],
          )

        expect(
          state.rolesByUid[
            'admin-1'
          ],
        ).toBe('admin')
        expect(
          state.auditLog,
        ).toEqual([])
        expect(
          readLogresAuditLog(
            state,
          ),
        ).toEqual([])
      },
    )

    it(
      'lets an admin assign roles and records an audit event',
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

        expect(
          state.rolesByUid[
            'mod-1'
          ],
        ).toBe('moderator')

        const log =
          readLogresAuditLog(
            state,
          )
        expect(
          log,
        ).toHaveLength(1)
        expect(
          log[0],
        ).toMatchObject({
          sequence: 1,
          actorUid:
            'admin-1',
          actorRole:
            'admin',
          action:
            'assign-role',
          targetUid:
            'mod-1',
        })
      },
    )

    it(
      'rejects role assignment by a non-admin',
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

        expect(() =>
          assignLogresRole(
            state,
            'mod-1',
            'someone',
            'moderator',
            101,
          ),
        ).toThrow(
          /below required admin/,
        )

        expect(() =>
          assignLogresRole(
            state,
            'plain-player',
            'someone',
            'moderator',
            101,
          ),
        ).toThrow(
          /below required admin/,
        )
      },
    )

    it(
      'lets a moderator mute a player but not another moderator',
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
        state =
          assignLogresRole(
            state,
            'admin-1',
            'mod-2',
            'moderator',
            100,
          )

        const muted =
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm1',
              subjectUid:
                'toxic-player',
              kind:
                'mute',
              reason:
                'spam',
              expiresAtSeconds:
                200,
            },
            150,
          )

        expect(
          getActiveLogresSanction(
            muted,
            'toxic-player',
            'mute',
            160,
          ),
        ).not.toBeNull()

        // Cannot sanction an equal-rank subject.
        expect(() =>
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm2',
              subjectUid:
                'mod-2',
              kind:
                'mute',
              reason:
                'x',
              expiresAtSeconds:
                null,
            },
            150,
          ),
        ).toThrow(
          /equal or higher role/,
        )
      },
    )

    it(
      'expires a timed sanction',
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

        state =
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm1',
              subjectUid:
                'p1',
              kind:
                'mute',
              reason:
                'spam',
              expiresAtSeconds:
                200,
            },
            150,
          )

        expect(
          getActiveLogresSanction(
            state,
            'p1',
            'mute',
            199,
          ),
        ).not.toBeNull()
        expect(
          getActiveLogresSanction(
            state,
            'p1',
            'mute',
            200,
          ),
        ).toBeNull()
      },
    )

    it(
      'rejects duplicate sanction keys and past-expiry sanctions',
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

        state =
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm1',
              subjectUid:
                'p1',
              kind:
                'mute',
              reason:
                'spam',
              expiresAtSeconds:
                null,
            },
            150,
          )

        expect(() =>
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm1',
              subjectUid:
                'p2',
              kind:
                'ban',
              reason:
                'x',
              expiresAtSeconds:
                null,
            },
            151,
          ),
        ).toThrow(
          /unique/,
        )

        expect(() =>
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm3',
              subjectUid:
                'p2',
              kind:
                'mute',
              reason:
                'x',
              expiresAtSeconds:
                100,
            },
            150,
          ),
        ).toThrow(
          /after issuance/,
        )
      },
    )

    it(
      'keeps the audit log append-only and frozen',
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
        state =
          issueLogresSanction(
            state,
            'mod-1',
            {
              sanctionKey:
                'm1',
              subjectUid:
                'p1',
              kind:
                'mute',
              reason:
                'spam',
              expiresAtSeconds:
                null,
            },
            150,
          )

        const log =
          readLogresAuditLog(
            state,
          )

        expect(
          log,
        ).toHaveLength(2)
        expect(
          Object.isFrozen(
            log,
          ),
        ).toBe(true)
        expect(
          log.map(
            (e) =>
              e.sequence,
          ),
        ).toEqual([
          1, 2,
        ])
      },
    )
  },
)
