import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds tutorial context without exporting private source or dialogue', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_tutorial_evidence.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres private tutorial evidence inspector self-test: PASS')
})
