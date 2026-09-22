import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('finds exact recovered live map references without exporting source text', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_live_confirmed_map_refs.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres live confirmed map reference inspector self-test: PASS')
})
