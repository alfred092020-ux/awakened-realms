import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('profiles Logres patch file-list formats without exporting resource payloads', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_patch_filelists.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres patch file-list format inspector self-test: PASS')
})
