import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('inspects a public Logres XAPK for patch network strings without URL queries', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_xapk_patch_network.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres public XAPK patch network inspector self-test: PASS')
})
