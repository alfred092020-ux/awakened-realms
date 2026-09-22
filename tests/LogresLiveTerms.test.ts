import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('scans live cache terms without exporting private strings or snippets', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_live_terms.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live bounded term inspector self-test: PASS')
})
