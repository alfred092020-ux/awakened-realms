import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('catalogs live patch MBN manifests without exporting payload bytes', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/catalog_live_patch_mbn.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres live patch MBN catalog self-test: PASS')
})
