import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT,
  LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT_SHA256,
  LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES,
  LOGRES_GLOBAL_DIFFERENTIAL_COUNTS,
  LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS,
  LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS,
  LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES,
  LOGRES_GLOBAL_DIFFERENTIAL_PROVENANCE,
  LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET,
} from '../src/game/logres/reverse/LogresGlobalDifferentialEvidence'

describe('MUI+UE Global vs reconstruction differential emulator', () => {
  it('locks the deterministic differential summary', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_PROVENANCE)
      .toBe('MUIUE_OFFLINE_GLOBAL_VS_RECONSTRUCTION_DIFFERENTIAL')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.checks).toBe(9)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.pass).toBe(5)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.implementationBugs).toBe(2)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.intentionalServerStubs).toBe(1)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.unknown).toBe(1)
  })

  it('confirms movement, response codes, bridge ordering and resource bindings', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES).toHaveLength(5)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES.map(x => x.id))
      .toContain('movement-global-fallback-and-collision')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES.map(x => x.id))
      .toContain('battle-entry-bridge-order')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_CONFIRMED_PASSES.map(x => x.id))
      .toContain('critical-resource-binding')
  })

  it('identifies the two evidence-backed battle-entry implementation bugs', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS).toHaveLength(2)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS[0].id)
      .toBe('battle-entry-retry-gate-enforcement')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS[0].actual)
      .toContain('immediately')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS[1].id)
      .toBe('playable-field-battle-entry-wiring')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_IMPLEMENTATION_BUGS[1].actual)
      .toContain('without recordEntryResponse')
  })

  it('keeps server-stub and unknown reward behavior separate from bugs', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES)
      .toHaveLength(2)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES[0].classification)
      .toBe('INTENTIONAL_SERVER_STUB')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_NON_BUG_DIVERGENCES[1].classification)
      .toBe('UNKNOWN')
  })

  it('emits a bounded non-auto-applying repair packet', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET.id)
      .toBe('DIFF-FIX-BATTLE-ENTRY-BOUNDARY')
    expect(LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET.autoApply).toBe(false)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET.autoMerge).toBe(false)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_REPAIR_PACKET.acceptance)
      .toContain(
        'Response code 2 must block another entry request until exactly 1.0 second elapses.',
      )
  })

  it('preserves authority ceilings', () => {
    expect(LOGRES_GLOBAL_DIFFERENTIAL_GUARDRAILS)
      .toContain(
        'Unknown retired-server semantics remain UNKNOWN rather than being filled from current JP.',
      )
    expect(LOGRES_GLOBAL_DIFFERENTIAL_COUNTS.fuzzerCasesAvailable).toBe(109)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT_SHA256).toHaveLength(64)
    expect(LOGRES_GLOBAL_DIFFERENTIAL_ARTIFACT)
      .toContain('global3024-differential-emulator')
  })
})
