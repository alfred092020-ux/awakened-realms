import { execFileSync } from 'node:child_process'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const verifier = path.resolve('scripts/logres/verify_visual_checkpoint.py')

function run(...args: string[]) {
  return JSON.parse(
    execFileSync('python3', [verifier, ...args], {
      encoding: 'utf8',
      maxBuffer: 1024 * 1024,
    }),
  )
}

describe('Logres visual checkpoint gate', () => {
  it('rejects black, missing-texture, and checkerboard catastrophes', () => {
    const result = run('--self-test')
    expect(result.pass).toBe(true)
    expect(result.cases.healthy.pass).toBe(true)
    expect(result.cases.black.pass).toBe(false)
    expect(result.cases.missing.pass).toBe(false)
    expect(result.cases.checker.pass).toBe(false)
  })

  it('keeps checkpoint invariants provenance-labelled without inventing unresolved history', () => {
    const result = run('--describe')
    expect(result.profiles.title.provenance).toEqual({
      assets: 'RECOVERED_GLOBAL',
      layout: 'SUPPORTED_INFERENCE_CURRENT_JP_LAYOUT',
      animation: 'UNRESOLVED_GLOBAL_LFLA',
    })
    expect(result.profiles.field.provenance).toMatchObject({
      map_binding: 'CONFIRMED_CURRENT_JP_002_000_00001',
      global_application: 'SUPPORTED_INFERENCE',
      spawn: 'RECONSTRUCTED',
    })
    expect(result.profiles.battle.provenance).toMatchObject({
      presentation: 'RECONSTRUCTED',
      historical_scene_composition: 'UNRESOLVED',
    })
  })
})
