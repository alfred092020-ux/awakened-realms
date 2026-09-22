import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('captures bounded native Z-argument arithmetic around addConvexhullVertices', () => {
  const output = execFileSync(
    'python3',
    ['-B','scripts/logres/inspect_public_terrain_z.py','--self-test'],
    { encoding:'utf8' },
  )
  expect(output).toContain('Logres public terrain Z inspector self-test: PASS')
})
