export const LOGRES_GLOBAL_3024_COMPLETENESS_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_STATIC_CLIENT_SURFACE_WITH_EXPLICIT_EXTERNAL_EVIDENCE_CEILINGS' as const

export const LOGRES_GLOBAL_3024_COMPLETENESS_SOURCE =
  Object.freeze({
    client: 'Global 3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    classesDexSha256:
      'd6b26b39f77566021ee670bb66a7e9a6eeff8372085b84ec3131a2d9dbfd3d7e',
    androidManifestSha256:
      '0580fe52a735f7d5ccd4dc1a4f74c0a4388519266538e5dfc20cadcc5a4cb11e',
    masterLedgerSha256:
      '6151ddc4ca0f4b5e03377d107eb117a5992ebc969c4339fbd62a24ef3916fc56',
  } as const)

export const LOGRES_GLOBAL_3024_COMPLETENESS_COUNTS =
  Object.freeze({
    lfsClassFamilies: 2372,
    lfsMethodEntries: 19467,
    lfsUnclassified: 0,
    gmclMessageIds: 631,
    gmclGeneratorSignatures: 214,
    gmclTypeMethodFamilies: 537,
    gmclTypeMethodEntries: 8125,
    gmclConstructorTypes: 533,
    aimingJavaFiles: 33,
    apkFiles: 156,
    apkBytes: 111901496,
    bootstrapMbnPackages: 23,
    decodedBootstrapMbnMembers: 461,
    bootstrapFilelistRecords: 27,
    recoveredOriginalSourcePaths: 139,
    recoveredSourceModuleFamilies: 22,
  } as const)

export const LOGRES_GLOBAL_3024_LFS_CATEGORY_COUNTS =
  Object.freeze({
    activityFeature: [3, 33],
    avatarProfile: [65, 696],
    battle: [352, 2498],
    bootScene: [109, 877],
    collaborationFeature: [4, 10],
    combatMisc: [4, 65],
    corePlayerSessionState: [1, 50],
    diagnosticSupport: [1, 2],
    economyShopGacha: [60, 572],
    emotionStampFeature: [9, 27],
    eventPvp: [105, 573],
    favoriteFeature: [3, 73],
    fieldWorld: [178, 1369],
    gplusSnsSdkFeature: [14, 103],
    gpsLocationFeature: [3, 75],
    handoverAccountFeature: [5, 89],
    itemsEquipment: [397, 3484],
    jobsProgression: [80, 441],
    miscClientFeature: [13, 76],
    networkProtocol: [31, 572],
    networkWebapiHelper: [1, 8],
    optionsSupportService: [10, 127],
    patchUpdate: [30, 215],
    platformAndroid: [15, 103],
    presentationPending: [46, 286],
    presentationResources: [158, 1177],
    questMission: [181, 1697],
    runtimeInfrastructure: [58, 393],
    sixthSenseFeature: [10, 80],
    socialClanPartyChatMail: [207, 1740],
    sortFilterHelpers: [38, 63],
    uiGui: [181, 1893],
  } as const)

export const LOGRES_GLOBAL_3024_COMPLETION_DEFINITION =
  Object.freeze([
    'Every first-party lfs class family is assigned to a recovered subsystem or explicit residual category.',
    'Every recovered GmCl message ID, type-method family and constructor schema is counted and named in the master ledger.',
    'Every com.aiming Java source recovered from classes.dex is listed.',
    'Every extracted APK file is hashed and listed and every decoded bootstrap MBN member is listed.',
    'Every recovered original source path and source-module family is listed.',
    'Unknown facts are restricted to external/server/runtime inputs, third-party internals, missing historical patch content or device-specific execution.',
  ] as const)

export const LOGRES_GLOBAL_3024_EVIDENCE_CEILINGS =
  Object.freeze([
    'Retired Global server authoritative validation, persistence, matchmaking, economy and dynamic-event decisions are not present in the APK.',
    'Historical production host endpoints, server tables and runtime payload values not cached in the APK remain external evidence.',
    'The Global GmCl transport chain is recovered as SplitToContract -> Snappy Compressor -> Packetize; linked Blowfish code has no proven active GmCl checkpoint.',
    'Remote patch assets absent from the recovered Global cache cannot be reconstructed byte-for-byte from the bootstrap APK.',
    'Historical store catalogs, server receipt verification, GCM scheduling and GPS reward/anti-abuse decisions remain server/service facts.',
    'Device-specific GPU rasterization, driver behavior and exact real-time presentation require original runtime hardware and matching assets.',
    'Historical hosted web copy and external collaboration/SDK service responses are not embedded client facts.',
    'Millennium Tree Global-2017 field-name to static terrain MultiID remains high supported inference because the Global server supplied those values separately.',
    'Third-party library internals are excluded from first-party Logres behavior coverage; only Aiming integration boundaries are recovered.',
  ] as const)

export const LOGRES_GLOBAL_3024_REVERSE_ENGINEERING_STATUS =
  'FIRST_PARTY_APK_SURFACE_FULLY_ACCOUNTED' as const
