import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('expands evidenced A4R4G4B4 map DDS pixels into deterministic private PNG data', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/hydrate_live_renderer_proof.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live renderer-proof hydration self-test: PASS')
})
