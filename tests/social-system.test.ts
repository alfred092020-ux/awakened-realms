import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  friendRequestDocumentId,
  relationshipFromRequests,
} from '../src/game/social/SocialService'

import type {
  FriendRequest,
} from '../src/game/social/SocialService'

function request(
  id: string,
  fromUid: string,
  toUid: string,
  status:
    FriendRequest['status'],
): FriendRequest {
  return {
    id,
    fromUid,
    toUid,
    status,
    createdAt:
      100,

    updatedAt:
      100,
  }
}

describe(
  'Social system',
  () => {
    it(
      'creates deterministic request document ids',
      () => {
        expect(
          friendRequestDocumentId(
            'alpha',
            'beta',
          ),
        ).toBe(
          'alpha__beta',
        )
      },
    )

    it(
      'detects outgoing requests',
      () => {
        const relation =
          relationshipFromRequests(
            'alpha',
            'beta',
            [
              request(
                'one',
                'alpha',
                'beta',
                'pending',
              ),
            ],
          )

        expect(
          relation.state,
        ).toBe(
          'outgoing',
        )
      },
    )

    it(
      'detects incoming requests',
      () => {
        const relation =
          relationshipFromRequests(
            'alpha',
            'beta',
            [
              request(
                'one',
                'beta',
                'alpha',
                'pending',
              ),
            ],
          )

        expect(
          relation.state,
        ).toBe(
          'incoming',
        )
      },
    )

    it(
      'accepted requests become friendships',
      () => {
        const relation =
          relationshipFromRequests(
            'alpha',
            'beta',
            [
              request(
                'one',
                'alpha',
                'beta',
                'accepted',
              ),
            ],
          )

        expect(
          relation.state,
        ).toBe(
          'friends',
        )
      },
    )

    it(
      'declined requests do not count as friends',
      () => {
        const relation =
          relationshipFromRequests(
            'alpha',
            'beta',
            [
              request(
                'one',
                'alpha',
                'beta',
                'declined',
              ),
            ],
          )

        expect(
          relation.state,
        ).toBe(
          'none',
        )
      },
    )
  },
)
