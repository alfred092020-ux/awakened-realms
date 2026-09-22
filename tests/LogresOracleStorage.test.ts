import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('reports Oracle storage and existing patch-cache bytes', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_oracle_storage.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Oracle Logres storage inspector self-test: PASS')
})
