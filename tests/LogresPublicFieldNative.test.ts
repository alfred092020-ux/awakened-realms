import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('filters current-Japanese native field symbols without a live download', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_public_field_native.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres public field native inspector self-test: PASS')
})
