import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('checks nested map evidence with synthetic records and privacy limits', () => {
  expect(() => execFileSync('python3', ['-B', 'scripts/logres/test_map_nested.py'], {
    encoding: 'utf8', stdio: 'pipe',
  })).not.toThrow()
})
