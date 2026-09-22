import { execFileSync } from 'node:child_process'
import { expect, it } from 'vitest'

it('derives bounded DDS pixel-format metadata from channel masks', () => {
  const output = execFileSync(
    'python3',
    ['-B', 'scripts/logres/inspect_live_map_dds_format.py', '--self-test'],
    { encoding: 'utf8' },
  )
  expect(output).toContain('Logres live map DDS format inspector self-test: PASS')
})
