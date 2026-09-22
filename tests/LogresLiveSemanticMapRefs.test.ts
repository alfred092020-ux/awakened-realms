import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('ranks structural map context while demoting resource-ID collisions', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_live_semantic_map_refs.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live semantic map reference inspector self-test: PASS')
})
