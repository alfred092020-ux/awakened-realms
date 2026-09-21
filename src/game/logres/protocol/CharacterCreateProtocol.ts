/*
 * Extracted from the Global Logres client.
 *
 * C_GMCL_CHAR_CREATE_REQ
 *
 * Argument order is preserved exactly.
 * Unknown integer meanings are intentionally
 * NOT renamed or guessed.
 */

export type LogresGender =
  | 0
  | 1

export type CharacterCreateRequest =
  readonly [
    0,
    string,
    LogresGender,
    1,
    1,
    1,
    number,
    number,
  ]

export function createCharacterCreateRequest(
  name: string,
  gender: LogresGender,
  randomA: number,
  randomB: number,
): CharacterCreateRequest {
  if (
    randomA < 1 ||
    randomA > 5 ||
    randomB < 1 ||
    randomB > 5
  ) {
    throw new Error(
      'Character-create random values must be 1..5',
    )
  }

  return [
    0,
    name,
    gender,
    1,
    1,
    1,
    randomA,
    randomB,
  ] as const
}
