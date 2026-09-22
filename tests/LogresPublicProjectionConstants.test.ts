import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('maps bounded ELF64 virtual float references to exact file-backed values', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_projection_constants.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres public projection constants inspector self-test: PASS')
})
