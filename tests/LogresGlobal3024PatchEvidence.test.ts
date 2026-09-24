import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_BACKGROUND_PATCH,
  LOGRES_GLOBAL_3024_MBN_FORMAT,
  LOGRES_GLOBAL_3024_PATCH_BOOTSTRAP,
  LOGRES_GLOBAL_3024_PATCH_LOGIN_BOUNDARY,
  LOGRES_GLOBAL_3024_PATCH_RECONSTRUCTED_FLOW,
  LOGRES_GLOBAL_3024_PATCH_RUNTIME,
  LOGRES_GLOBAL_3024_PATCH_SOURCE,
  LOGRES_GLOBAL_3024_PATCH_STATES,
  LOGRES_GLOBAL_3024_PATCH_STORAGE,
  LOGRES_GLOBAL_3024_PATCH_UNRESOLVED,
} from '../src/game/logres/patch/LogresGlobal3024PatchEvidence'

describe(
  'Global 3.0.24 patch/bootstrap evidence',
  () => {
    it(
      'anchors patch evidence to the signed Global client',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_SOURCE,
        ).toMatchObject({
          clientVersion: '3.0.24',
          apkSha256:
            '7424aa5b84fc52358a955dd1bb6b6d0b31f50f6b58d58e592ece4257cec17943',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
        })
      },
    )

    it(
      'preserves bootstrap integrity and the service-host substitution anomaly',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_BOOTSTRAP,
        ).toMatchObject({
          fileListRecordCount: 27,
          fileListDeclaredBytes: 8183956,
          exactPathChecksumMatches: 26,
          exactPathSizeMatches: 26,
          binFileListPackageCount: 23,
          binFileListMemberCount: 461,
        })

        expect(
          LOGRES_GLOBAL_3024_PATCH_BOOTSTRAP
            .fileListRecordFields,
        ).toEqual([
          'sha1',
          'byteSize',
          'relativePath',
          'timestamp',
        ])

        const host =
          LOGRES_GLOBAL_3024_PATCH_BOOTSTRAP
            .serviceHostSubstitutionEvidence

        expect(host).toMatchObject({
          declaredPath: 'servicehost.json',
          declaredSize: 1056,
          alternatePackagedPath:
            '_servicehost.json',
          alternatePackagedSize: 1056,
        })
        expect(
          host.declaredSha1,
        ).toBe(
          host.alternatePackagedSha1,
        )
        expect(
          host.declaredSha1,
        ).not.toBe(
          host.releasePackagedSha1,
        )
      },
    )

    it(
      'models the recovered MBN container without inventing compression modes',
      () => {
        expect(
          LOGRES_GLOBAL_3024_MBN_FORMAT,
        ).toMatchObject({
          fixedHeaderBytes: 8,
          requiredReservedValue: 0,
          manifestEncoding:
            'utf-8-json-array',
          bundledPackageCount: 23,
          bundledMemberCount: 461,
          zlibMemberCount: 451,
          rawMemberCount: 10,
          storedMemberBytes: 7188987,
          expandedMemberBytes: 34632646,
        })

        expect(
          LOGRES_GLOBAL_3024_MBN_FORMAT
            .compressionTypes,
        ).toEqual({
          raw: 0,
          zlib: 1,
        })
      },
    )

    it(
      'keeps remote file-list verification in the login sequence',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_LOGIN_BOUNDARY,
        ).toMatchObject({
          verificationBehavior:
            'login::VerifyPatchDataBehavior',
          accountLoginEntry:
            'ReleaseScene_AccountLogIn::startPatch',
          remoteFileListCallbackShape:
            'onReceiveRemoteFilelist(int, string const&)',
        })

        expect(
          LOGRES_GLOBAL_3024_PATCH_LOGIN_BOUNDARY
            .resourceRefreshMethods,
        ).toEqual(
          expect.arrayContaining([
            'ResourceManager::updatePatchRootPath',
            'ResourceManager::updatePatchFileList',
          ]),
        )
      },
    )

    it(
      'preserves the scheduler-worker-downloader-cache architecture',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_RUNTIME
            .scheduler.methods,
        ).toEqual(
          expect.arrayContaining([
            'calculateHash',
            'detectRemoteChanges',
            'eraseUnnecessaryLocalFiles',
            'setDownloadFiles',
            'assignWorker',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_PATCH_RUNTIME
            .downloader.ioCallbacks,
        ).toEqual([
          'WriteFileCallback',
          'SeekFileCallback',
          'ProgressCallback',
        ])

        expect(
          LOGRES_GLOBAL_3024_PATCH_RUNTIME
            .cache.methods,
        ).toContain(
          'downloadWhenIsNotCached',
        )
      },
    )

    it(
      'keeps state names separate from unresolved enum values',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_STATES,
        ).toEqual([
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
        ])

        expect(
          LOGRES_GLOBAL_3024_PATCH_UNRESOLVED,
        ).toContain(
          'numeric values of patcher::RunningState',
        )
      },
    )

    it(
      'distinguishes full pre-download from background/JIT resource fetching',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BACKGROUND_PATCH,
        ).toMatchObject({
          preDownloadListPath:
            'system/pre_download.txt',
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
        })
      },
    )

    it(
      'connects patch storage back into the resource manager while retaining unknowns',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PATCH_STORAGE
            .methods,
        ).toEqual(
          expect.arrayContaining([
            'loadData',
            'loadMicroBin',
            'isMicroBinExist',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_PATCH_RECONSTRUCTED_FLOW,
        ).toEqual(
          expect.arrayContaining([
            'compare remote metadata against local file information and hashes',
            'remove unnecessary local files',
            'select changed or missing files',
            'dispatch patch-download jobs to patch workers',
            'serve deferred resources through patch cache when background mode permits',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_PATCH_UNRESOLVED,
        ).toEqual(
          expect.arrayContaining([
            'exact historical production CDN base URL returned by hostentry',
            'exact historical contents of system/pre_download.txt',
            'complete historical remote patch manifest and payload set',
          ]),
        )
      },
    )
  },
)
