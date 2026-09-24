export const LOGRES_GLOBAL_3024_PLATFORM_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_ANDROID_JAVA_JNI_PLATFORM_SURFACE' as const

export const LOGRES_GLOBAL_3024_PLATFORM_SOURCE =
  Object.freeze({
    client: 'Global 3.0.24',
    packageName: 'com.aiming.logresjrpg',
    versionCode: 2432,
    versionName: '3.0.24',
    classesDexSha256:
      'd6b26b39f77566021ee670bb66a7e9a6eeff8372085b84ec3131a2d9dbfd3d7e',
    androidManifestSha256:
      '0580fe52a735f7d5ccd4dc1a4f74c0a4388519266538e5dfc20cadcc5a4cb11e',
    evidenceArtifactSha256:
      '8436d072e2f4855ee7bc521bee0c5a564eb11f52c107a194934db91eefdad371',
  } as const)

export const LOGRES_GLOBAL_3024_ANDROID_SURFACE =
  Object.freeze({
    minSdk: 14,
    targetSdk: 26,
    aimingJavaFiles: 33,
    components: Object.freeze({
      activities: 3,
      services: 2,
      receivers: 1,
      providers: 1,
    } as const),
    launchActivity: 'com.aiming.lfs.LFSActivity',
    application: 'com.aiming.lfs.LFSApplication',
    deepLink: Object.freeze({
      scheme: 'logresjrpg',
      host: '*',
    } as const),
    permissions: Object.freeze([
      'INTERNET',
      'ACCESS_NETWORK_STATE',
      'ACCESS_WIFI_STATE',
      'BILLING',
      'WAKE_LOCK',
      'GET_TASKS',
      'GCM_RECEIVE',
      'GCM_REGISTER',
      'C2D_MESSAGE',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_JNI_CALLBACKS =
  Object.freeze([
    'LFSActivity.nativeOnTrimMemory(int)',
    'ApplicationUtility.nativeIsDebugMode()',
    'ApplicationUtility.nativeOnGetCacheDirectory(String)',
    'AudioController.fadeoutMusic(float)',
    'AudioController.pauseBGM()',
    'AuMarketHelper.nativeOnDispatchEvent(String,String)',
    'BillingProcessor.nativeOnDispatchEvent(String,String)',
    'NativeIntent.nativeOnOpenURI(String)',
    'LocationManagerContractController.nativeDisabledLocationServiceCallbackFunction()',
    'LocationManagerContractController.nativeLocationRequestCallbackFunction(boolean,float,float)',
    'LocationManagerContractController.nativeUsedMockLocationServiceCallbackFunction()',
    'PushNotificationContract.nativeOnRegistered(boolean,String)',
  ] as const)

export const LOGRES_GLOBAL_3024_APP_LIFECYCLE =
  Object.freeze({
    libraryLoad:
      'Loads libgame.so, with ABI-specific APK extraction fallback into app-private lib storage.',
    create:
      'Initializes KDDI market for the KDDI package or Google billing otherwise, then constructs PermissionRequester.',
    resume:
      'Checks Google Play Services.',
    pause:
      'Optionally terminates the process after an explicit exit request.',
    trimMemory:
      'Forwards Android memory pressure to native.',
    newIntent:
      'Forwards logresjrpg deep-link URI to native on the GL thread.',
    backKey:
      'Navigates the active Cocos2dxWebView first, otherwise forwards the key to the GL surface.',
  } as const)

export const LOGRES_GLOBAL_3024_BILLING_PLATFORM =
  Object.freeze({
    google:
      'Google IAB helper with product inventory, purchase, consume, receipt JSON and signature boundaries.',
    nativeEvents: Object.freeze([
      'OnAvailableProducts',
      'OnPurchaseFinished',
      'OnPurchaseCancelled',
      'OnPurchaseError',
      'OnConsumeFinished',
      'OnConsumeError',
    ] as const),
    kddi:
      'KDDI package selects AuMarketHelper; the Java implementation in this APK is stubbed except for its native event boundary.',
    nativeSurface: Object.freeze({
      classes: 23,
      methods: 143,
    } as const),
  } as const)

export const LOGRES_GLOBAL_3024_PUSH_PLATFORM =
  Object.freeze({
    registration:
      'Legacy GCM registration returns success and registration ID through nativeOnRegistered.',
    delivery:
      'GCMBroadcastReceiver schedules GCMIntentService through Firebase JobDispatcher.',
    contentKeys: Object.freeze([
      'ticker',
      'title',
      'text',
      'dialog',
      'positive',
      'negative',
    ] as const),
    nativeSurface: Object.freeze({
      classes: 7,
      methods: 44,
    } as const),
  } as const)

export const LOGRES_GLOBAL_3024_LOCATION_PLATFORM =
  Object.freeze({
    permissions: Object.freeze([
      'ACCESS_FINE_LOCATION',
      'ACCESS_COARSE_LOCATION',
    ] as const),
    provider: 'Google Play Services location API',
    nativeSurface: Object.freeze({
      classes: 12,
      methods: 108,
    } as const),
    mockDetection:
      'Optional check tests Android mock_location plus root/su indicators and reports a dedicated native callback.',
  } as const)

export const LOGRES_GLOBAL_3024_PLATFORM_BRIDGES =
  Object.freeze({
    keychain:
      'SharedPreferences file named keychain with string read/write/clear.',
    browser:
      'ACTION_VIEW URI with NEW_TASK.',
    mailer:
      'ACTION_SEND text/plain with email, subject and body extras.',
    audio:
      'Audio-focus loss triggers native two-second music fade and BGM pause.',
    cacheDirectory:
      'Permission-gated external app files cache path with internal-files fallback.',
    systemInformation:
      Object.freeze([
        'ISO3 country',
        'device model/product',
        'Android release',
        'keep-screen-on toggle',
        'native/Dalvik heap JSON',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_THIRD_PARTY_BOUNDARY =
  Object.freeze({
    packageCounts: Object.freeze({
      google: 386,
      androidSupport: 354,
      smartBeat: 64,
      firebase: 29,
      cocos2dx: 24,
      androidArch: 10,
    } as const),
    classification:
      'THIRD_PARTY_LIBRARIES_WITH_FIRST_PARTY_AIMING_GLUE_ONLY',
  } as const)

export const LOGRES_GLOBAL_3024_PLATFORM_UNRESOLVED =
  Object.freeze([
    'Historical store catalog contents and server-side receipt validation policy are runtime/server facts.',
    'Historical GCM sender ID and production push scheduling policy are runtime/server supplied.',
    'Server-side GPS reward and anti-abuse decisions are not recoverable from Android glue alone.',
    'Third-party library internals are outside first-party Logres reverse-engineering scope.',
  ] as const)
