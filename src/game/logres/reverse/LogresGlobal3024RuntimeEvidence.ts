export const LOGRES_GLOBAL_3024_RUNTIME_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    libgameArmv7Sha256:
      '2d5e0bd6eaf362540fbbb164a25ede0b5c163785d71fa926769f40fa61e2842c',
    nativeIndex:
      '/home/ubuntu/logres/index/global-3024-native.sqlite',
    nativeIndexBuiltAt:
      '2026-09-23 23:46:13',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_SURFACE_COUNTS =
  Object.freeze({
    fileMethods: 8,
    fileSystemMethods: 22,
    packageStorageMethods: 9,
    patchStorageMethods: 9,
    microBinMethods: 9,
    microBinCacheStorageMethods: 15,
    microBinLoadableStorageMethods: 7,
    localStorageUserAccessorMethods: 36,
    localStorageSerializableReferences: 8,
    base64Symbols: 7,
    jsonHelpers: 15,
    oneupTimerSymbols: 3,
    oneupSchedulerSymbols: 11,
    logSymbols: 22,
    gameInformationSymbols: 18,
    appDelegateSymbols: 4,
    applicationSymbols: 19,
    commandLineOptions: 18,
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_FILESYSTEM =
  Object.freeze({
    fileType:
      'lfs::File',
    fileOperations:
      Object.freeze([
        'open',
        'read',
        'write',
        'seek',
        'size',
        'close',
      ] as const),
    fileSystemType:
      'lfs::FileSystem',
    fileSystemOperations:
      Object.freeze([
        'CreateDir',
        'FileDir',
        'FileExtention',
        'FileName',
        'FindFiles',
        'ForceDirectories',
        'GetFileSize',
        'GetFileSizeAndLastUpdate',
        'GetLastUpdate',
        'GetPackageRootPath',
        'IsDirExist',
        'IsFileExist',
        'IsFileExistInPackage',
        'NormalizePath',
        'ReadFile',
        'ReadFileFromPackage',
        'RemoveFile',
        'RemoveFileExtention',
        'RenameFile',
        'SetLastUpdate',
        'WriteAppendFile',
        'WriteFile',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_RESOURCE_STORAGE =
  Object.freeze({
    packageStorage:
      Object.freeze([
        'initialize',
        'loadData',
        'loadMicroBin',
        'isExist',
        'isMicroBinExist',
        'update',
      ] as const),
    patchStorage:
      Object.freeze([
        'initialize(path)',
        'loadData',
        'loadMicroBin',
        'isExist',
        'isMicroBinExist',
        'update',
      ] as const),
    microBin:
      Object.freeze([
        'parseHeader',
        'getData',
        'isExist',
        'FileInfo',
      ] as const),
    cacheStorage:
      Object.freeze([
        'cache',
        'getMicroBin',
        'findFiles',
        'isCachedMicroBin',
        'loadData',
        'touch',
        'uncache',
        'uncacheImmediately',
        'uncacheAll',
        'update',
      ] as const),
    loadableStorage:
      Object.freeze([
        'cacheMicroBin',
        'findFiles',
        'isCachedMicroBin',
        'setupFileNameTbl',
      ] as const),
    interpretation:
      'package-and-patch-resources-are-a-separate-storage-boundary-from-user-local-state',
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_LOCAL_STATE =
  Object.freeze({
    accessor:
      'lfs::LocalStorageUserAccessor',
    lifecycle:
      Object.freeze([
        'initialize',
        'loadCommon',
        'setAccount',
        'loadAccount',
        'save',
        'clear',
        'reset',
        'terminate',
      ] as const),
    pathBoundaries:
      Object.freeze([
        'rootDirectoryPath',
        'commonDirectoryPath',
        'accountDirectoryPath',
        'createFilePath(LocalStorageUserDataCategory)',
        'createFilePath(LocalStorageUserDataCategoryForCommon)',
      ] as const),
    valueBoundaries:
      Object.freeze([
        'get(LocalStorageUserDataCategory, ..., ISerializable&)',
        'set(LocalStorageUserDataCategory, ..., ISerializable const&)',
        'get(LocalStorageUserDataCategoryForCommon, ..., ISerializable&)',
        'set(LocalStorageUserDataCategoryForCommon, ..., ISerializable const&)',
        'setJson',
        'Setting::jsonFormat',
        'Setting::setJsonValue',
        'Setting::setJsonObject',
      ] as const),
    interpretation:
      'common-and-account-scoped-persistent-local-state-are-distinct',
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_SERIALIZATION =
  Object.freeze({
    firstPartyJsonNamespace:
      'lfs::json',
    jsonOperations:
      Object.freeze([
        'json11Parse',
        'parse(oneup::JSON::Value&)',
        'getJsonBooleanValueOrDefault',
        'getJsonS32ValueOrDefault',
        'getJsonU32ValueOrDefault',
        'getJsonU64ValueOrDefault',
        'getJsonF32ValueOrDefault',
        'getJsonF64ValueOrDefault',
        'getJsonStringValueOrDefault',
        'getStringArray',
      ] as const),
    base64Namespace:
      'lfs::base64',
    base64Operations:
      Object.freeze([
        'Encode',
        'Decode',
        'base64Encode',
        'base64Decode',
      ] as const),
    thirdPartyPrimitives:
      Object.freeze([
        'json11',
        'oneup::JSON',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_SCHEDULING =
  Object.freeze({
    ownership:
      'ENGINE_OR_MIDDLEWARE_ONEUP',
    timer:
      Object.freeze({
        type:
          'oneup::Timer',
        operations:
          Object.freeze([
            'Timer(bool, float)',
            'update',
            '~Timer',
          ] as const),
      }),
    scheduler:
      Object.freeze({
        type:
          'oneup::Scheduler',
        operations:
          Object.freeze([
            'add',
            'remove',
            'search',
            'update',
            'adjustUpdateTime',
            'executeTasks',
            'dischargeMessage',
            'waitUntilAllTaskFinished',
            'clear',
          ] as const),
      }),
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_LOGGING =
  Object.freeze({
    facade:
      'lfs::log',
    operations:
      Object.freeze([
        'initialize',
        'terminate',
        'pause',
        'resume',
        'initializeConsoleOutputLog',
        'initializeDebugOutputLog',
        'initializeFileLog',
        'log_print',
        'push',
        'outputProtcolBufferLog',
        'toAndroidLogLevel',
        'toSeverityLevel',
      ] as const),
    underlyingDependency:
      'Boost.Log',
    interpretation:
      'Logres-owned-lfs-facade-over-Boost-Log-and-platform-sinks',
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_COMMAND_LINE =
  Object.freeze([
    'AccountName',
    'BottomLayoutGuide',
    'Console',
    'FilterLogLevel',
    'FirstScene',
    'Height',
    'LoggingStackTrace',
    'LoginLite',
    'Mute',
    'NoWebView',
    'PositionX',
    'PositionY',
    'PrintWebApiLog',
    'ServiceVersion',
    'SkipTitle',
    'SkipWorldSelect',
    'TopLayoutGuide',
    'Width',
  ] as const)

export const LOGRES_GLOBAL_3024_RUNTIME_LIFECYCLE =
  Object.freeze({
    platformLifecycleOwner:
      'lfs::AppDelegate',
    platformHooks:
      Object.freeze([
        'applicationDidFinishLaunching',
        'applicationDidEnterBackground',
        'applicationWillEnterForeground',
      ] as const),
    gameLifecycleOwner:
      'lfs::GameInformation',
    gameLifecycleSurface:
      Object.freeze([
        'initializeForPreBeginGame',
        'beginGame',
        'initializeGameComponents',
        'endGame',
        'terminateGameComponents',
        'terminate',
        'onTrimMemory',
      ] as const),
    commandLineOwner:
      'GameInformation::setCommandLine',
    applicationUtilityNamespace:
      'lfs::application',
    applicationUtilities:
      Object.freeze([
        'Initialize',
        'Exit',
        'CleanAppDirectory',
        'GetPackageName',
        'GetServiceVersion',
        'GetServiceVersionInt',
        'GetStoreVersion',
        'GetDataDirectory',
        'GetCacheDirectory',
        'GetTmpDirectory',
        'IsProvideKddi',
      ] as const),
    interpretation:
      'AppDelegate exposes platform lifecycle, GameInformation exposes game-component lifecycle, and lfs::application exposes platform directory/version/exit utilities',
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_BOUNDARIES =
  Object.freeze({
    logresOwned:
      Object.freeze([
        'lfs::File',
        'lfs::FileSystem',
        'lfs::PackageStorage',
        'lfs::PatchStorage',
        'lfs::MicroBin',
        'lfs::MicroBinCacheStorage',
        'lfs::MicroBinLoadableStorage',
        'lfs::LocalStorageUserAccessor',
        'lfs::json',
        'lfs::base64',
        'lfs::log',
        'lfs::GameInformation',
        'lfs::AppDelegate',
        'lfs::application',
        'lfs::CommandLineOption',
      ] as const),
    engineOrThirdParty:
      Object.freeze([
        'oneup::Timer',
        'oneup::Scheduler',
        'oneup::JSON',
        'json11',
        'Boost.Log',
        'std::__ndk1',
        'cocos2d',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_RUNTIME_UNRESOLVED =
  Object.freeze([
    'exact serialized file names and on-disk JSON schemas for every LocalStorageUserDataCategory',
    'which local-storage categories are written before versus after account login',
    'exact startup call order among AppDelegate, lfs::application, and GameInformation beyond the exported ownership surfaces',
    'MicroBin compression algorithm values behind FileInfo::CompressType',
    'scheduler thread-count and task-priority policy beyond the exported oneup surface',
    'log retention and rotation policy plus production severity thresholds',
  ] as const)
