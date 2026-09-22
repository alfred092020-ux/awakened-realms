import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds patch endpoints and versions without exporting private source or URL queries', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_patch_system.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres private patch system inspector self-test: PASS')
})
