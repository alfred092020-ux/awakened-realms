import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds packaged source metadata without exporting source or dialogue', () => {
  expect(() => execFileSync('python3', ['-B', 'scripts/logres/test_source_inventory.py'], {
    encoding: 'utf8', stdio: 'pipe',
  })).not.toThrow()
})
