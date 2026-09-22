import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('reports structural JSON context for live map IDs without string values', () => {
  const output=execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_live_json_map_context.py','--self-test'],
    {encoding:'utf8'},
  )
  expect(output).toContain('Logres live JSON map context inspector self-test: PASS')
})
