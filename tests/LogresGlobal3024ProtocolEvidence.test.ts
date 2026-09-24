import { describe, expect, it } from 'vitest'

import {
  LOGRES_GLOBAL_3024_ACCOUNT_LOGIN_RESULTS,
  LOGRES_GLOBAL_3024_CHAR_CREATE_RESULTS,
  LOGRES_GLOBAL_3024_CHAR_LOGIN_RESULTS,
  LOGRES_GLOBAL_3024_CORE_TYPES,
  LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE,
  LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES,
  LOGRES_GLOBAL_3024_PROTOCOL_SOURCE,
  LOGRES_GLOBAL_3024_PROTOCOL_SURFACE,
  LOGRES_GLOBAL_3024_PROTOCOL_UNRESOLVED,
  LOGRES_GLOBAL_3024_SERVER_PUSHES,
} from '../src/game/logres/protocol/LogresGlobal3024ProtocolEvidence'

describe('Global 3.0.24 GmCl protocol evidence', () => {
  it('anchors the catalog to original Global artifacts', () => {
    expect(LOGRES_GLOBAL_3024_PROTOCOL_SOURCE).toMatchObject({
      clientVersion: '3.0.24',
      libgameArm64Sha256: 'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
      provenance: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_NATIVE_PROTOCOL',
    })
    expect(LOGRES_GLOBAL_3024_PROTOCOL_SURFACE).toEqual({
      functionIds: 631, clientMessages: 205, serverMessages: 239,
      responseMessages: 187, generatorSignatures: 214, constructorTypes: 533,
    })
  })

  it('records the proven message envelope without inventing transport framing', () => {
    expect(LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE).toMatchObject({
      payloadBuffer: 'oneup::Buffer',
      functionIdBytes: 4,
      functionIdPosition: 'first-field',
      functionIdByteOrder: 'little-endian-on-original-AArch64-client',
    })
    expect(LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE.senderProperties)
      .toEqual({ ContractId: '0x31318435', Encryption: 'bool' })
    expect(LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE.packetizeFrame)
      .toMatchObject({ marker: '0x01', sequence: 'uint32 little-endian incrementing counter' })
    expect(LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE.senderBehavior)
      .toContain('call oneup::Connection::sendData')
    expect(LOGRES_GLOBAL_3024_MESSAGE_ENVELOPE.transportChain)
      .toMatchObject({
        checkpointOrder: ['SplitToContract', 'Compressor', 'Packetize'],
        compression: { algorithm: 'Snappy', minimumAttemptBytes: 0x401 },
        encryption: {
          defaultValue: false,
          activeCryptoCheckpoint: false,
          blowfishLinked: true,
        },
      })
  })

  it('recovers login and onboarding opcodes and result values', () => {
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.accountLogin.request)
      .toMatchObject({ functionId: 1946813788, hex: '0x740a055c' })
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.characterCreate.request)
      .toMatchObject({
        functionId: 510385705,
        schema: 'int, string, int, int, int, int, int, int',
      })
    expect(LOGRES_GLOBAL_3024_ACCOUNT_LOGIN_RESULTS)
      .toMatchObject({ SUCCESS: 1, INVALID_SESSION_TOKEN: 5, CLIENT_VERSION_ERROR: 6 })
    expect(LOGRES_GLOBAL_3024_CHAR_CREATE_RESULTS)
      .toEqual({ SUCCESS: 0, DUPLICATION: 1, WORD_FILTER: 2, OTHER_ERR: 3 })
    expect(LOGRES_GLOBAL_3024_CHAR_LOGIN_RESULTS)
      .toMatchObject({ SUCCESS: 1, SPAWN: 4, ERR_WORLD_IS_FULL: 7 })
  })

  it('recovers field movement and interaction schemas', () => {
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.fieldSelect.request)
      .toMatchObject({ functionId: 268550344, schema: 't_FieldUID, int, int' })
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.characterMove.request)
      .toMatchObject({
        functionId: 2106585959,
        hex: '0x7d8ff367',
        schema: 'float, t_AreaUID, t_MapPos, t_MapPos, t_arrGridCoord',
      })
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.characterTalk.request.functionId)
      .toBe(1396260262)
    expect(LOGRES_GLOBAL_3024_CORE_TYPES)
      .toMatchObject({ t_AreaUID: 'int, int', t_MapPos: 'float, float', t_GridCoord: 'int, int' })
  })

  it('recovers encounter and battle protocol IDs', () => {
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.battleEntry.request)
      .toMatchObject({ functionId: 4261373906, hex: '0xfdff67d2' })
    expect(LOGRES_GLOBAL_3024_PROTOCOL_MESSAGES.battleUseSkill.request)
      .toMatchObject({ functionId: 3604126339, hex: '0xd6d29a83' })
    expect(LOGRES_GLOBAL_3024_SERVER_PUSHES.battleResult.functionId)
      .toBe(1528823482)
    expect(LOGRES_GLOBAL_3024_SERVER_PUSHES.battleDrop.functionId)
      .toBe(1250495900)
  })

  it('recovers server projections needed by the playable slice', () => {
    expect(LOGRES_GLOBAL_3024_SERVER_PUSHES).toMatchObject({
      npcAppear: { functionId: 455001580 },
      enemyAppear: { functionId: 4268853861 },
      itemInfo: { functionId: 4110668784 },
      questResult: { functionId: 1638040888 },
    })
  })

  it('keeps only genuine external or dormant semantics unresolved', () => {
    expect(LOGRES_GLOBAL_3024_PROTOCOL_UNRESOLVED)
      .not.toContain('transport bytes below the confirmed oneup Packetize layer, if any')
    expect(LOGRES_GLOBAL_3024_PROTOCOL_UNRESOLVED)
      .toContain('server-side validation and persistence behavior not present in the client binary')
    expect(LOGRES_GLOBAL_3024_PROTOCOL_UNRESOLVED)
      .toContain('non-GmCl or dormant uses of the linked oneup::Blowfish capability, if any')
  })
})
