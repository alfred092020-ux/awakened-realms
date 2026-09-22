import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('bounds Convexhull source tracing without a live download', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_convexhull_source.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres public Convexhull source inspector self-test: PASS')
})
