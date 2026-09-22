import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('decodes evidenced map schema and preserves repeated UV poses', () => {
  expect(() => execFileSync('python3', ['-B', 'scripts/logres/test_map_schema.py'], {
    encoding: 'utf8', stdio: 'pipe',
  })).not.toThrow()
})
