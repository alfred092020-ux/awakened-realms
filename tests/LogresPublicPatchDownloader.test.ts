import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('parses and path-validates the public Logres patch download plan', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/download_public_patch.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres public patch downloader self-test: PASS')
})
