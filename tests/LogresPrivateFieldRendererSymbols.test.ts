import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds allowlisted renderer symbols without exporting private source', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_field_renderer_symbols.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres private field renderer symbol inspector self-test: PASS')
})
