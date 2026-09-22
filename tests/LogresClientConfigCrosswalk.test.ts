import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('builds a structural Global↔Japanese config crosswalk without string payloads', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/build_client_config_crosswalk.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres config localization crosswalk self-test: PASS')
})
