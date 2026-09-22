import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('sanitizes public Logres host-entry metadata without leaking query secrets', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_hostentry.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres public host-entry inspector self-test: PASS')
})
