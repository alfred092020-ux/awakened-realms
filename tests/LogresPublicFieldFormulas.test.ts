import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('filters bounded native field formula instruction metadata offline', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_field_formulas.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres public field formula inspector self-test: PASS')
})
