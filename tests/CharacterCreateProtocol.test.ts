import { describe, expect, it } from 'vitest'
import { createCharacterCreateRequest } from '../src/game/logres/protocol/CharacterCreateProtocol'

describe('character creation request boundary', () => {
  it('preserves request order and both inclusive random endpoints', () => {
    expect(createCharacterCreateRequest('Test', 0, 1, 5))
      .toEqual([0, 'Test', 0, 1, 1, 1, 1, 5])
    expect(createCharacterCreateRequest('Test', 1, 5, 1))
      .toEqual([0, 'Test', 1, 1, 1, 1, 5, 1])
  })

  it.each([NaN, Infinity, -Infinity, 0, 6, 1.5, 4.5])(
    'rejects invalid first random field %s',
    (value) => {
      expect(() => createCharacterCreateRequest('Test', 0, value, 1))
        .toThrow()
    },
  )

  it.each([NaN, Infinity, -Infinity, 0, 6, 1.5, 4.5])(
    'rejects invalid second random field %s',
    (value) => {
      expect(() => createCharacterCreateRequest('Test', 0, 1, value))
        .toThrow()
    },
  )
})
