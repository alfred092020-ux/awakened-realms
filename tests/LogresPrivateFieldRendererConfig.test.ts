import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'
it('extracts renderer config keys and numeric values without private strings', () => {
  const output=execFileSync('python3',['-B','scripts/logres/inspect_private_field_renderer_config.py','--self-test'],{encoding:'utf8'})
  expect(output).toContain('Logres private field renderer config inspector self-test: PASS')
})
