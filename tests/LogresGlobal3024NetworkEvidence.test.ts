import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_AUTH,
  LOGRES_GLOBAL_3024_HOSTENTRY,
  LOGRES_GLOBAL_3024_LOGIN_BEHAVIORS,
  LOGRES_GLOBAL_3024_NETWORK_AUTHORITY,
  LOGRES_GLOBAL_3024_NETWORK_SOURCE,
  LOGRES_GLOBAL_3024_NETWORK_SURFACE_COUNTS,
  LOGRES_GLOBAL_3024_NETWORK_UNRESOLVED,
  LOGRES_GLOBAL_3024_TRANSPORT,
} from '../src/game/logres/protocol/LogresGlobal3024NetworkEvidence'

describe(
  'Global 3.0.24 network/auth evidence',
  () => {
    it(
      'anchors the protocol surface to the original Global client',
      () => {
        expect(
          LOGRES_GLOBAL_3024_NETWORK_SOURCE,
        ).toMatchObject({
          clientVersion: '3.0.24',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
        })

        expect(
          LOGRES_GLOBAL_3024_NETWORK_SURFACE_COUNTS,
        ).toEqual({
          functionIdSymbols: 631,
          binaryGeneratorMethods: 214,
          networkSessionMethods: 343,
          authAgentMethods: 25,
          hostEntryMethods: 51,
          loginNamespaceMethods: 47,
        })
      },
    )

    it(
      'keeps GmCl binary gameplay messaging distinct from connection/system control',
      () => {
        expect(
          LOGRES_GLOBAL_3024_TRANSPORT,
        ).toMatchObject({
          connection:
            'oneup::Connection',
          gamePayloadGenerator:
            'ClientGmClProtoProcedureBinaryGenerator',
          gamePayloadBuffer:
            'oneup::Buffer',
          framingBytes:
            'oneup Packetize 0x01 + uint32 sequence + base-128 payload length + 4-byte little-endian GmCl FUNCTION_ID + typed payload',
          socketTransportBeyondPacketize:
            'UNRESOLVED',
        })

        expect(
          LOGRES_GLOBAL_3024_TRANSPORT
            .connectionStates,
        ).toEqual(
          expect.arrayContaining([
            'CSConnecting',
            'CSInPreparation',
            'CSEstablished',
            'CSClosing',
          ]),
        )
      },
    )

    it(
      'preserves the account/session/character login authority boundaries',
      () => {
        expect(
          LOGRES_GLOBAL_3024_AUTH
            .requestSurface,
        ).toEqual(
          expect.arrayContaining([
            'C_GMCL_ACCOUNT_LOGIN_REQ',
            'C_GMCL_ACCOUNT_REAUTH_REQ',
            'C_GMCL_CHAR_LOGIN_REQ',
            'C_GMCL_CHAR_CREATE_REQ',
            'C_GMCL_ZONEIN_REQ',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_AUTH
            .accountLoginResultCodes,
        ).toEqual(
          expect.arrayContaining([
            'E_GMCL_ACCLOGIN_SUCCESS',
            'E_GMCL_ACCLOGIN_NOT_AGREEMENT',
            'E_GMCL_ACCLOGIN_INVALID_SESSION_TOKEN',
            'E_GMCL_ACCLOGIN_CLIENT_VERSION_ERROR',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_AUTH
            .tokenSurface,
        ).toContain(
          't_arrSecureSessionToken',
        )
      },
    )

    it(
      'records HostEntry as the service/world/webview discovery source',
      () => {
        expect(
          LOGRES_GLOBAL_3024_HOSTENTRY
            .serviceCategories,
        ).toEqual(
          expect.arrayContaining([
            'authentication',
            'character',
            'item',
            'party',
            'chat',
            'event',
            'mission',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_HOSTENTRY
            .worldFields,
        ).toEqual(
          expect.arrayContaining([
            'world_layout',
            'gameServers',
            'apiServers',
            'patchServerURL',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_HOSTENTRY
            .webViewFields,
        ).toContain(
          'terms',
        )
      },
    )

    it(
      'retains the native staged login behaviors without inventing their exact branch predicates',
      () => {
        expect(
          LOGRES_GLOBAL_3024_LOGIN_BEHAVIORS,
        ).toEqual(
          expect.arrayContaining([
            'GetHostentryBehavior',
            'CheckServiceStateBehavior',
            'VerifyApplicationVersionBehavior',
            'VerifyPatchDataBehavior',
            'AuthenticationBehavior',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_NETWORK_AUTHORITY,
        ).toMatchObject({
          hostDiscovery:
            'HostEntry-driven',
          gameMessaging:
            'typed-GmCl-binary-procedures',
          accountLogin:
            'server-result-code-driven',
        })

        expect(
          LOGRES_GLOBAL_3024_NETWORK_UNRESOLVED,
        ).toContain(
          'transport bytes below the confirmed oneup Packetize layer, if any',
        )
      },
    )
  },
)
