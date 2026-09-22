import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('decompresses recovered zlib patch file lists and profiles their real structure', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_private_patch_filelist_zlib.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres decompressed patch file-list inspector self-test: PASS')
})
