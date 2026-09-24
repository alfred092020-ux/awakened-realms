import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_ARTIFACT,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_CEILINGS,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_DRIFT_GUARDS,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_POLICY,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_PROVENANCE,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_SELF_TESTS,
  LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE,
} from '../src/game/logres/reverse/LogresGlobal3024OfflineProtocolTwinEvidence'

describe('Global 3.0.24 offline protocol twin evidence', () => {
  it('is explicitly offline and Global-authoritative', () => {
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_PROVENANCE)
      .toBe('CONFIRMED_GLOBAL_3_0_24_OFFLINE_PROTOCOL_TWIN')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_POLICY.networkAccess)
      .toBe('NO_SOCKET_OR_REMOTE_SERVER_ACCESS')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_POLICY.serverAuthority)
      .toContain('explicit deterministic offline stubs')
  })

  it('encodes the recovered Global oneup transport chain', () => {
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.contractId).toBe(0x31318435)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.splitToContract)
      .toContain('nestedBufferLength')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.compressorThreshold)
      .toBe(0x401)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.compressorRaw)
      .toBe('0x00 + raw bytes')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.compressorCompressed)
      .toContain('Snappy')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_WIRE.encryptionCheckpoint)
      .toBe(false)
  })

  it('accounts for every recovered procedure as a fixture', () => {
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES.totalMessages).toBe(631)
    expect(
      LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES.exactTopLevelWireFixtures
      + LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES.schemaOnlyOrPartialFixtures
    ).toBe(631)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES.criticalExactClientFrames)
      .toBe(10)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_FIXTURES.criticalServerAuthorityStubs)
      .toBe(20)
  })

  it('protects original Global schemas from current-JP drift', () => {
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_DRIFT_GUARDS.characterMove)
      .toContain('no trailing t_WarpUID')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_DRIFT_GUARDS.battleUseSkill)
      .toContain('no extra single target field')
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_DRIFT_GUARDS.characterCreate)
      .toContain('eight-field Global form')
  })

  it('round-trips raw and compressed offline frames without hiding ceilings', () => {
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_SELF_TESTS.rawRoundTrip).toBe(true)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_SELF_TESTS.snappyRoundTrip).toBe(true)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_ARTIFACT.sha256).toHaveLength(64)
    expect(LOGRES_GLOBAL_3024_OFFLINE_TWIN_CEILINGS)
      .toContain(
        'Offline replay proves recovered client wire/framing behavior; it does not recreate retired production server state.',
      )
  })
})
