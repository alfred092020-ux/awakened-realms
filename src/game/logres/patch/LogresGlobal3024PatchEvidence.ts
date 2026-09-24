export const LOGRES_GLOBAL_3024_PATCH_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    apkSha256:
      '7424aa5b84fc52358a955dd1bb6b6d0b31f50f6b58d58e592ece4257cec17943',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_APK_AND_NATIVE_SURFACE',
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_BOOTSTRAP =
  Object.freeze({
    serviceHostReleaseTemplate:
      'https://capi-prd.logres-jrpg.com:8443/lfsapi/hostentry/${platform}/${version}',
    fileListName: 'filelist.txt',
    binFileListName: 'binfilelist.txt',
    fileListRecordFields:
      Object.freeze([
        'sha1',
        'byteSize',
        'relativePath',
        'timestamp',
      ] as const),
    fileListRecordCount: 27,
    fileListDeclaredBytes: 8183956,
    exactPathChecksumMatches: 26,
    exactPathSizeMatches: 26,
    serviceHostSubstitutionEvidence:
      Object.freeze({
        declaredPath: 'servicehost.json',
        declaredSize: 1056,
        declaredSha1:
          '2de29b949f594143179b76907570649ad3893598',
        releasePackagedSize: 147,
        releasePackagedSha1:
          '7c543f915248c541c1102668313793b67b3b0404',
        alternatePackagedPath:
          '_servicehost.json',
        alternatePackagedSize: 1056,
        alternatePackagedSha1:
          '2de29b949f594143179b76907570649ad3893598',
        interpretation:
          'bootstrap-list-record-matches-alternate-environment-host-table-not-release-only-host-table',
      } as const),
    binFileListPackageCount: 23,
    binFileListMemberCount: 461,
    binFileListSemantics:
      'tab-separated-microbin-package-to-inner-member-name-index',
  } as const)

export const LOGRES_GLOBAL_3024_MBN_FORMAT =
  Object.freeze({
    fixedHeaderBytes: 8,
    headerFields:
      Object.freeze([
        'reserved:uint32le',
        'manifestSize:uint32le',
      ] as const),
    requiredReservedValue: 0,
    manifestEncoding: 'utf-8-json-array',
    recordFields:
      Object.freeze([
        'name',
        'size',
        'offset',
        'compresstype',
        'dst_size?',
      ] as const),
    payloadOffset: '8+manifestSize',
    compressionTypes:
      Object.freeze({
        raw: 0,
        zlib: 1,
      } as const),
    bundledPackageCount: 23,
    bundledMemberCount: 461,
    zlibMemberCount: 451,
    rawMemberCount: 10,
    storedMemberBytes: 7188987,
    expandedMemberBytes: 34632646,
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_LOGIN_BOUNDARY =
  Object.freeze({
    verificationBehavior:
      'login::VerifyPatchDataBehavior',
    verificationMethods:
      Object.freeze([
        'onEnter',
        'onReceiveRemoteFilelist',
        'onExit',
      ] as const),
    accountLoginEntry:
      'ReleaseScene_AccountLogIn::startPatch',
    remoteFileListCallbackShape:
      'onReceiveRemoteFilelist(int, string const&)',
    resourceRefreshMethods:
      Object.freeze([
        'ResourceManager::updatePatchRootPath',
        'ResourceManager::updatePatchFileList',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_RUNTIME =
  Object.freeze({
    facade:
      Object.freeze({
        className: 'patcher::Patcher',
        methods:
          Object.freeze([
            'initialize',
            'setup',
            'start',
            'stop',
            'terminate',
            'update',
            'getState',
            'getCache',
            'getProgressTotal',
            'getProgressSubTotal',
            'getProgressString',
            'getDownloadFileCount',
            'getDownloadedFileCount',
            'getDownloadFileSize',
            'getDownloadedFileSize',
            'getStorageFreeSize',
            'removeLocalList',
            'wipeFiles',
          ] as const),
      } as const),
    scheduler:
      Object.freeze({
        className:
          'patcher::PatchScheduler',
        methods:
          Object.freeze([
            'initialize',
            'calculateHash',
            'appendLocalFileList',
            'generateFileInfo',
            'compareFile',
            'detectRemoteChanges',
            'eraseUnnecessaryLocalFiles',
            'setDownloadFiles',
            'proceedQueue',
            'assignWorker',
            'getFinishedWorker',
            'freeWorker',
            'getTotalFileSize',
            'getRunningState',
            'start',
            'stop',
            'terminate',
            'update',
            'main',
          ] as const),
      } as const),
    worker:
      Object.freeze({
        className: 'patcher::PatchWorker',
        methods:
          Object.freeze([
            'initialize',
            'setJob',
            'getJob',
            'start',
            'stop',
            'terminate',
            'main',
            'breakOut',
            'isBreakOut',
            'isFinished',
          ] as const),
      } as const),
    downloadJob:
      Object.freeze({
        className:
          'patcher::PatchDownloadJob',
        methods:
          Object.freeze([
            'proceed',
            'getProgress',
            'cancel',
          ] as const),
      } as const),
    downloader:
      Object.freeze({
        className:
          'patcher::MemoryEfficientDownloader',
        ioCallbacks:
          Object.freeze([
            'WriteFileCallback',
            'SeekFileCallback',
            'ProgressCallback',
          ] as const),
        methods:
          Object.freeze([
            'initialize',
            'request',
            'download',
            'cancel',
            'terminate',
            'getProgress',
            'isCanceled',
          ] as const),
      } as const),
    cache:
      Object.freeze({
        className: 'patcher::PatchCache',
        methods:
          Object.freeze([
            'hasFile',
            'add',
            'purge',
            'download',
            'downloadWhenIsNotCached',
          ] as const),
      } as const),
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_STATES =
  Object.freeze([
    'invalid',
    'uninitialized',
    'ready',
    'preparing',
    'cleanupFiles',
    'pickupFiles',
    'downloading',
    'completed',
    'canceled',
    'failed',
    'failedOutOfStorageSpace',
    'idle',
  ] as const)

export const LOGRES_GLOBAL_3024_BACKGROUND_PATCH =
  Object.freeze({
    persistedModeType:
      'download_option::BackgroundPatchMode',
    loadMode:
      'download_option::loadBackgroundPatchMode',
    saveMode:
      'download_option::saveBackgroundPatchMode',
    modeWindow:
      'download_option::DownloadOptionWindow',
    backgroundIndicator:
      'indicator::BackgroundPatchDisplay',
    preDownloadListPath:
      'system/pre_download.txt',
    preDownloadRegexLog:
      'preDownloadRegex: %s',
    additionalPreDownloadHook:
      'patcher::Patcher::s_additionalPreDownloadFile',
    jitFailureHook:
      'patcher::Patcher::s_jitDownloadFailedBehavior',
    offSemantics:
      'all-data-downloaded-before-game-start',
    onSemantics:
      'background-or-just-in-time-resource-downloads-allowed',
    cacheBoundary:
      'patcher::PatchCache::downloadWhenIsNotCached',
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_STORAGE =
  Object.freeze({
    className: 'PatchStorage',
    methods:
      Object.freeze([
        'initialize',
        'loadData',
        'loadMicroBin',
        'isExist',
        'isMicroBinExist',
        'update',
      ] as const),
    resourceManagerMicroBinMethods:
      Object.freeze([
        'ResourceManager::Impl::findStorageContainsMicroBin',
        'ResourceManager::Impl::loadBlockWaitMicroBin',
        'ResourceManager::Impl::unloadMicroBin',
      ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_PATCH_RECONSTRUCTED_FLOW =
  Object.freeze([
    'load packaged service-host/bootstrap metadata',
    'obtain remote file-list data during login verification',
    'compare remote metadata against local file information and hashes',
    'remove unnecessary local files',
    'select changed or missing files',
    'build download queue and aggregate byte/file counts',
    'dispatch patch-download jobs to patch workers',
    'stream files through the memory-efficient downloader',
    'update patch storage/cache and resource-manager file-list/root-path state',
    'serve deferred resources through patch cache when background mode permits',
  ] as const)

export const LOGRES_GLOBAL_3024_PATCH_UNRESOLVED =
  Object.freeze([
    'numeric values of patcher::RunningState',
    'exact patcher::Parameters field layout and historical production values',
    'exact historical production CDN base URL returned by hostentry',
    'exact worker concurrency count selected by the Global 3.0.24 runtime',
    'exact HTTP retry, resume, and backoff policy for every failure mode',
    'exact semantics of the fourth bootstrap filelist integer beyond being a timestamp-like value',
    'exact release-build reason for servicehost.json metadata matching _servicehost.json',
    'exact historical contents of system/pre_download.txt',
    'complete historical remote patch manifest and payload set',
  ] as const)
