import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  normalizePresence,
} from '../src/game/social/PresenceService'

import {
  buildMultiplayerRoomDraft,
} from '../src/game/social/MultiplayerService'

describe(
  'Realtime multiplayer foundation',
  () => {
    it(
      'treats missing presence as offline',
      () => {
        expect(
          normalizePresence(
            'player-a',
            undefined,
          ),
        ).toEqual({
          uid:
            'player-a',

          online:
            false,

          lastChanged:
            0,
        })
      },
    )

    it(
      'parses live presence',
      () => {
        expect(
          normalizePresence(
            'player-a',
            {
              online:
                true,

              lastChanged:
                5000,
            },
          ),
        ).toEqual({
          uid:
            'player-a',

          online:
            true,

          lastChanged:
            5000,
        })
      },
    )

    it(
      'creates a two-player invited room',
      () => {
        expect(
          buildMultiplayerRoomDraft(
            'host',
            'guest',
            1000,
          ),
        ).toEqual({
          hostUid:
            'host',

          guestUid:
            'guest',

          status:
            'invited',

          createdAt:
            1000,

          updatedAt:
            1000,
        })
      },
    )
  },
)
