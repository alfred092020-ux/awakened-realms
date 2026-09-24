export const LOGRES_GLOBAL_JP_LINEAGE_PROVENANCE =
  'GLOBAL_ORIGINAL_PLUS_CURRENT_JP_LINEAGE_WITH_STRICT_VERSION_LABELS' as const

export const LOGRES_GLOBAL_JP_BOOTSTRAP_LINEAGE =
  Object.freeze({
    global3024: Object.freeze({
      endpoint:
        'https://capi-prd.logres-jrpg.com:8443/lfsapi/hostentry/\u0024{platform}/\u0024{version}',
      classification: 'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
      dnsOn20260924: 'NO_DNS_RESULT',
    } as const),
    currentJp: Object.freeze({
      endpoint:
        'https://capi-sp.mmo-logres.com:8443/cusapi/hostentry/\u0024{platform}/\u0024{version}',
      patchBase: 'https://prd-cdn.mmo-logres.com/patch',
      webviewBase: 'https://webview.mmo-logres.com',
      gamePort: 8800,
      classification: 'CONFIRMED_CURRENT_JP',
    } as const),
    sharedParserKeys: Object.freeze([
      'allow_connect_gmsv',
      'api',
      'apiserver',
      'app_review_url',
      'authentication',
      'can_create_new_account',
      'create_time',
      'cusapi_state',
      'env',
      'gameserver',
      'patchserver',
      'provider_environment',
      'update',
      'version_information',
      'webview',
      'world',
      'world_layout',
      'worldnumber',
    ] as const),
    sharedServiceCategories: Object.freeze([
      'account',
      'ad',
      'authentication',
      'campaign',
      'character',
      'chat',
      'clan',
      'community',
      'friend',
      'in_app_purchase',
      'item',
      'job',
      'mercenary',
      'party',
      'push_notification',
      'ranking',
      'service_state',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_JP_PROTOCOL_LINEAGE =
  Object.freeze({
    globalUniqueNames: 631,
    currentJpMappedNames: 1057,
    sharedNames: 470,
    sharedSameOpcode: 470,
    sharedChangedOpcode: 0,
    sameOpcodeRateAmongSharedPercent: 100,
    globalNamesStillSameInCurrentJpPercent: 74.48,
    criticalCore: Object.freeze({
      accountLogin: '0x740a055c',
      characterCreate: '0x1e6bde29',
      characterLogin: '0x24f8b2ea',
      characterMove: '0x7d8ff367',
      fieldInfo: '0x5789022a',
      fieldSelect: '0x1001c0c8',
      zoneIn: '0x8634bc61',
      areaEnter: '0x6dff0f05',
      npcAppear: '0x1b1ec5ec',
      enemyAppear: '0xfe718a65',
      battleEntry: '0xfdff67d2',
      battleUseSkill: '0xd6d29a83',
      battleResult: '0x5b1ffeba',
      questReady: '0x1acb9ad4',
      questNextState: '0x111cd41c',
    } as const),
  } as const)

export const LOGRES_GLOBAL_JP_EXACT_ASSET_LINEAGE =
  Object.freeze({
    globalFilesCompared: 14,
    sameBasenameInCurrentJp: 6,
    exactByteMatches: 6,
    files: Object.freeze([
      'info.mbn',
      'json_resource.mbn',
      'system.mbn',
      'tutorial.mbn',
      'Battle.mbn',
      '002_000_00001.mbn',
    ] as const),
    millenniumTreeMapPackageSha256:
      'ff0cd4ba4e84af9586c4921147fb463a70bd4f822ea10b456eea8eb5ea3a444c',
  } as const)

export const LOGRES_GLOBAL_JP_TRANSFER_TIERS =
  Object.freeze({
    confirmedGlobal:
      'Directly recovered from the Global 3.0.24 APK/native/cache and authoritative for that client.',
    confirmedCrossVersion:
      'Exact Global and JP identity proven mechanically by opcode, schema key or SHA256 byte match.',
    supportedLineageInference:
      'Current-JP runtime behavior is consistent with unchanged Global architecture/protocol/assets, but lacks a Global-era primary record.',
    currentJpOnly:
      'Current server endpoints, ports, world state, hosted content, patch generations and JP-only features; never retroactively relabel as historical Global.',
  } as const)

export const LOGRES_GLOBAL_JP_MILLENNIUM_TREE =
  Object.freeze({
    currentJpAreaId: '002_001_00200',
    currentJpMapFileId: '002_000_00001',
    currentJpClassification: 'CONFIRMED_CURRENT_JP',
    globalPackagePresent: true,
    globalJpPackageByteIdentical: true,
    historicalGlobalClassification: 'SUPPORTED_INFERENCE',
    missingUpgradeEvidence:
      'A Global-era S_GMCL_AREA_ENTER payload, warp/area table, or equivalent primary record pairing Millennium Tree with terrain MultiID 002_000_00001.',
  } as const)

export const LOGRES_GLOBAL_JP_LINEAGE_GUARDRAILS =
  Object.freeze([
    'Current JP hostnames, ports, world counts, patch generation IDs and hosted page contents are not historical Global facts.',
    'Current JP-only procedures or features cannot be projected backward into Global 3.0.24.',
    'Current server database values, quest/map assignments and dynamic event state require independent Global-era corroboration before being labeled original Global.',
    'No direct evidence has been recovered that Global production accounts or databases were literally merged into the JP production database.',
  ] as const)

export const LOGRES_GLOBAL_JP_LINEAGE_ARTIFACTS =
  Object.freeze({
    lineage:
      '0ae455b5b3bb670b534019b416b82b8d2a6b9fa1cd4eb22d930a9d70c1c62c78',
    assets:
      'fdd18d37d30fea1b6c581a4a0522f09a04014c02dafe411370032c76376b118d',
    transport:
      '54ba63ba244ef0361337896bd457e23a54f766d7a95739bf70e769d38400f321',
  } as const)
