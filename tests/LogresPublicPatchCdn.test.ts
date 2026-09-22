import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('probes public Logres patch CDN metadata without retaining asset payloads', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_patch_cdn.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres public patch CDN inspector self-test: PASS')
})
