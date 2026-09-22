import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('targets projection/depth helpers and preserves conditional arithmetic mnemonics', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_field_projection.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres public field projection inspector self-test: PASS')
})
