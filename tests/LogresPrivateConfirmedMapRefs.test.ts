import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds only exact references to independently confirmed recovered map IDs', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_confirmed_map_refs.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres confirmed private map reference inspector self-test: PASS')
})
