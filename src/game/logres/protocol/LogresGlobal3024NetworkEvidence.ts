export const LOGRES_GLOBAL_3024_NETWORK_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
  } as const)

export const LOGRES_GLOBAL_3024_NETWORK_SURFACE_COUNTS =
  Object.freeze({
    functionIdSymbols: 631,
    binaryGeneratorMethods: 214,
    networkSessionMethods: 343,
    authAgentMethods: 25,
    hostEntryMethods: 51,
    loginNamespaceMethods: 47,
  } as const)

export const LOGRES_GLOBAL_3024_TRANSPORT =
  Object.freeze({
    connection:
      'oneup::Connection',
    gameContract:
      'ClientGmClProtoContract<NetworkSession, ClientGmClProtoSender<ClientGmClProtoProcedureBinaryGenerator>, ClientGmClProtoProcedureBinaryParser>',
    gamePayloadGenerator:
      'ClientGmClProtoProcedureBinaryGenerator',
    gamePayloadBuffer:
      'oneup::Buffer',
    systemControlGenerator:
      'System::*SystemProcedureJSONGenerator',
    connectionStates:
      Object.freeze([
        'CSIdle',
        'CSConnecting',
        'CSInPreparation',
        'CSEstablished',
        'CSClosing',
        'CSTerminate',
        'CSException',
      ] as const),
    framingBytes:
      'UNRESOLVED',
  } as const)

export const LOGRES_GLOBAL_3024_AUTH =
  Object.freeze({
    requestSurface:
      Object.freeze([
        'C_GMCL_ACCOUNT_LOGIN_REQ',
        'C_GMCL_ACCOUNT_REAUTH_REQ',
        'C_GMCL_CHAR_LOGIN_REQ',
        'C_GMCL_CHAR_CREATE_REQ',
        'C_GMCL_ZONEIN_REQ',
        'C_GMCL_FIELD_INFO_REQ',
      ] as const),
    accountLoginResultCodes:
      Object.freeze([
        'E_GMCL_ACCLOGIN_SUCCESS',
        'E_GMCL_ACCLOGIN_UNKNOWN',
        'E_GMCL_ACCLOGIN_REAUTH_SUCCESS',
        'E_GMCL_ACCLOGIN_NOT_AGREEMENT',
        'E_GMCL_ACCLOGIN_DISALLOW',
        'E_GMCL_ACCLOGIN_INVALID_SESSION_TOKEN',
        'E_GMCL_ACCLOGIN_CLIENT_VERSION_ERROR',
        'E_GMCL_ACCLOGIN_SUSPENDED',
      ] as const),
    tokenSurface:
      Object.freeze([
        'account_token',
        'device_token',
        'session_token',
        't_arrSecureSessionToken',
        't_ReauthCode',
      ] as const),
    agentOperations:
      Object.freeze([
        'RegisterAccount',
        'GetSessionToken',
        'accountLogin',
        'agreeToTerms',
        'requestWorldIDFromAccountToken',
        'requestCusApiKey',
        'accountReauth',
        'DecryptSessionToken',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_HOSTENTRY =
  Object.freeze({
    serviceCategories:
      Object.freeze([
        'authentication',
        'account',
        'character',
        'item',
        'job',
        'party',
        'friend',
        'chat',
        'clan',
        'community',
        'mercenary',
        'event',
        'event_src_data',
        'mission',
        'push_notification',
        'in_app_purchase',
        'email_login',
        'service_state',
      ] as const),
    worldFields:
      Object.freeze([
        'world',
        'world_layout',
        'gameServers',
        'apiServers',
        'patchServerURL',
      ] as const),
    webViewFields:
      Object.freeze([
        'terms',
        'info',
        'news',
        'help',
        'support',
        'law',
        'inquiry',
        'warning',
        'event_point_base',
      ] as const),
    behavior:
      Object.freeze([
        'loadHostEntry',
        'loadHostEntryFromText',
        'loadHostEntryFromJson',
        'setupWorldLayout',
        'switchHost',
        'getHostNameFromWorldNumber',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_LOGIN_BEHAVIORS =
  Object.freeze([
    'GetHostentryBehavior',
    'CheckServiceStateBehavior',
    'VerifyApplicationVersionBehavior',
    'VerifyPatchDataBehavior',
    'CallLoginMethodBehavior',
    'AuthenticationBehavior',
    'CallReloginMethodBehavior',
    'LoginWarningBehavior',
    'ExitServiceBehavior',
  ] as const)

export const LOGRES_GLOBAL_3024_NETWORK_AUTHORITY =
  Object.freeze({
    hostDiscovery:
      'HostEntry-driven',
    gameMessaging:
      'typed-GmCl-binary-procedures',
    connectionLifecycle:
      'oneup-state-machine',
    accountLogin:
      'server-result-code-driven',
    secureSession:
      'server-token-and-reauth-code-driven',
    worldSelection:
      'authentication-and-HostEntry-world-state',
  } as const)

export const LOGRES_GLOBAL_3024_NETWORK_UNRESOLVED =
  Object.freeze([
    'exact numeric values of every FUNCTION_ID constant',
    'exact wire packet header and framing byte layout',
    'exact transport encryption and compression behavior for each message class',
    '2017 production HostEntry payload values and server addresses',
    'server-side validation semantics beyond exposed result codes',
  ] as const)
