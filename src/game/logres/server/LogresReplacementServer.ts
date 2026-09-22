import type {
  CharacterCreateRequest,
} from '../protocol/CharacterCreateProtocol'

/*
 * RECONSTRUCTED replacement-server emulator.
 *
 * The original character-create response body
 * has not been recovered. This module provides
 * an authority boundary for the reconstructed
 * server contract without claiming historical
 * packet contents.
 *
 * It currently runs in-process for development,
 * so it is not yet a remote trust boundary.
 * Persistent production authority must move
 * behind the replacement backend.
 */

export interface ReconstructedCharacterCreateResponse {
  provenance:
    'RECONSTRUCTED'

  accepted:
    true

  nextState:
    'tutorial-field'
}

function assertCharacterCreateRequest(
  request:
    readonly unknown[],
): asserts request is CharacterCreateRequest {
  if (
    request.length !== 8 ||
    request[0] !== 0 ||
    typeof request[1] !==
      'string' ||
    request[1].length === 0 ||
    (
      request[2] !== 0 &&
      request[2] !== 1
    ) ||
    request[3] !== 1 ||
    request[4] !== 1 ||
    request[5] !== 1 ||
    !Number.isInteger(
      request[6],
    ) ||
    !Number.isInteger(
      request[7],
    ) ||
    (
      request[6] as number
    ) < 1 ||
    (
      request[6] as number
    ) > 5 ||
    (
      request[7] as number
    ) < 1 ||
    (
      request[7] as number
    ) > 5
  ) {
    throw new Error(
      'Replacement server rejected malformed C_GMCL_CHAR_CREATE_REQ',
    )
  }
}

export async function
submitCharacterCreateToReplacementServer(
  request:
    readonly unknown[],
): Promise<
  ReconstructedCharacterCreateResponse
> {
  assertCharacterCreateRequest(
    request,
  )

  return {
    provenance:
      'RECONSTRUCTED',

    accepted:
      true,

    nextState:
      'tutorial-field',
  }
}
