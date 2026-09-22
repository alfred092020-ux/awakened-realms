import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('compares paired live ASTC and __ans DDS map packages without payload export', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_live_map_variants.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live map variant inspector self-test: PASS')
})
