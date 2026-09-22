import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('tracks bounded setupEntities Convexhull vector dataflow including conditional branches', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_public_setupentities_vectors.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres setupEntities Convexhull vector inspector self-test: PASS')
})
