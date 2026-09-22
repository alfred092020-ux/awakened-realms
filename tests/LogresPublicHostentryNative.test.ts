import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds bounded public HostEntry native strings', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_hostentry_native.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres public HostEntry native inspector self-test: PASS')
})
