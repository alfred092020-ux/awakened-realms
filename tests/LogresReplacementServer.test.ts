import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  createCharacterCreateRequest,
} from '../src/game/logres/protocol/CharacterCreateProtocol'

import {
  submitCharacterCreateToReplacementServer,
} from '../src/game/logres/server/LogresReplacementServer'

describe(
  'reconstructed Logres character-create authority',
  () => {
    it(
      'accepts the exact client request shape and returns a labeled tutorial continuation',
      async () => {
        const response =
          await submitCharacterCreateToReplacementServer(
            createCharacterCreateRequest(
              'Test',
              0,
              1,
              5,
            ),
          )

        expect(
          response,
        ).toEqual({
          provenance:
            'RECONSTRUCTED',

          accepted:
            true,

          nextState:
            'tutorial-field',
        })
      },
    )

    it.each([
      {
        malformed: [
          0,
          'Test',
          2,
          1,
          1,
          1,
          1,
          1,
        ],
      },
      {
        malformed: [
          0,
          'Test',
          0,
          2,
          1,
          1,
          1,
          1,
        ],
      },
      {
        malformed: [
          0,
          'Test',
          0,
          1,
          1,
          1,
          1.5,
          1,
        ],
      },
      {
        malformed: [
          0,
          '',
          0,
          1,
          1,
          1,
          1,
          1,
        ],
      },
    ])(
      'rejects malformed server-bound tuple',
      async ({
        malformed,
      }) => {
        await expect(
          submitCharacterCreateToReplacementServer(
            malformed,
          ),
        ).rejects.toThrow(
          'Replacement server rejected malformed C_GMCL_CHAR_CREATE_REQ',
        )
      },
    )
  },
)
