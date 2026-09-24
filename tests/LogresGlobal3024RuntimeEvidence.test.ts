import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_RUNTIME_BOUNDARIES,
  LOGRES_GLOBAL_3024_RUNTIME_COMMAND_LINE,
  LOGRES_GLOBAL_3024_RUNTIME_FILESYSTEM,
  LOGRES_GLOBAL_3024_RUNTIME_LIFECYCLE,
  LOGRES_GLOBAL_3024_RUNTIME_LOCAL_STATE,
  LOGRES_GLOBAL_3024_RUNTIME_LOGGING,
  LOGRES_GLOBAL_3024_RUNTIME_RESOURCE_STORAGE,
  LOGRES_GLOBAL_3024_RUNTIME_SCHEDULING,
  LOGRES_GLOBAL_3024_RUNTIME_SERIALIZATION,
  LOGRES_GLOBAL_3024_RUNTIME_SOURCE,
  LOGRES_GLOBAL_3024_RUNTIME_SURFACE_COUNTS,
  LOGRES_GLOBAL_3024_RUNTIME_UNRESOLVED,
} from '../src/game/logres/reverse/LogresGlobal3024RuntimeEvidence'

describe(
  'Global 3.0.24 runtime infrastructure evidence',
  () => {
    it(
      'anchors runtime facts to original Global native evidence',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SOURCE,
        ).toMatchObject({
          clientVersion: '3.0.24',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
          provenance:
            'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_SURFACE',
        })

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SURFACE_COUNTS,
        ).toMatchObject({
          fileMethods: 8,
          fileSystemMethods: 22,
          packageStorageMethods: 9,
          patchStorageMethods: 9,
          microBinMethods: 9,
          microBinCacheStorageMethods: 15,
          microBinLoadableStorageMethods: 7,
          localStorageUserAccessorMethods: 36,
          commandLineOptions: 18,
        })
      },
    )

    it(
      'separates packaged resources from persistent user state',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_RESOURCE_STORAGE
            .interpretation,
        ).toBe(
          'package-and-patch-resources-are-a-separate-storage-boundary-from-user-local-state',
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_RESOURCE_STORAGE
            .cacheStorage,
        ).toEqual(
          expect.arrayContaining([
            'cache',
            'getMicroBin',
            'touch',
            'uncache',
            'uncacheAll',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_FILESYSTEM
            .fileSystemOperations,
        ).toEqual(
          expect.arrayContaining([
            'ReadFileFromPackage',
            'WriteFile',
            'RemoveFile',
            'NormalizePath',
          ]),
        )
      },
    )

    it(
      'preserves common and account-scoped local persistence as separate boundaries',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LOCAL_STATE
            .pathBoundaries,
        ).toEqual(
          expect.arrayContaining([
            'commonDirectoryPath',
            'accountDirectoryPath',
            'createFilePath(LocalStorageUserDataCategory)',
            'createFilePath(LocalStorageUserDataCategoryForCommon)',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LOCAL_STATE
            .lifecycle,
        ).toEqual(
          expect.arrayContaining([
            'loadCommon',
            'setAccount',
            'loadAccount',
            'save',
            'terminate',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LOCAL_STATE
            .interpretation,
        ).toBe(
          'common-and-account-scoped-persistent-local-state-are-distinct',
        )
      },
    )

    it(
      'records first-party serialization helpers without claiming dependencies as Logres-owned',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SERIALIZATION
            .jsonOperations,
        ).toContain(
          'json11Parse',
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SERIALIZATION
            .base64Operations,
        ).toEqual(
          expect.arrayContaining([
            'Encode',
            'Decode',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_BOUNDARIES
            .engineOrThirdParty,
        ).toEqual(
          expect.arrayContaining([
            'oneup::Timer',
            'oneup::Scheduler',
            'json11',
            'Boost.Log',
            'std::__ndk1',
          ]),
        )
      },
    )

    it(
      'keeps oneup scheduling explicitly outside the lfs-owned abstraction surface',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SCHEDULING
            .ownership,
        ).toBe(
          'ENGINE_OR_MIDDLEWARE_ONEUP',
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_SCHEDULING
            .scheduler.operations,
        ).toEqual(
          expect.arrayContaining([
            'add',
            'update',
            'executeTasks',
            'waitUntilAllTaskFinished',
            'clear',
          ]),
        )
      },
    )

    it(
      'records lifecycle ownership and only the Global 3.0.24 command-line surface',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LIFECYCLE,
        ).toMatchObject({
          platformLifecycleOwner:
            'lfs::AppDelegate',
          gameLifecycleOwner:
            'lfs::GameInformation',
          commandLineOwner:
            'GameInformation::setCommandLine',
          applicationUtilityNamespace:
            'lfs::application',
        })

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LIFECYCLE
            .gameLifecycleSurface,
        ).toEqual(
          expect.arrayContaining([
            'initializeForPreBeginGame',
            'initializeGameComponents',
            'terminateGameComponents',
            'terminate',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_COMMAND_LINE,
        ).toHaveLength(
          18,
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_COMMAND_LINE,
        ).toEqual(
          expect.arrayContaining([
            'FirstScene',
            'SkipTitle',
            'SkipWorldSelect',
            'ServiceVersion',
            'LoginLite',
            'NoWebView',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_COMMAND_LINE,
        ).not.toContain(
          'DebugResourcePatch',
        )
      },
    )

    it(
      'keeps the Logres logging facade distinct from Boost.Log internals',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LOGGING,
        ).toMatchObject({
          facade:
            'lfs::log',
          underlyingDependency:
            'Boost.Log',
        })

        expect(
          LOGRES_GLOBAL_3024_RUNTIME_LOGGING
            .operations,
        ).toEqual(
          expect.arrayContaining([
            'initialize',
            'terminate',
            'initializeFileLog',
            'outputProtcolBufferLog',
          ]),
        )
      },
    )

    it(
      'states evidence ceilings instead of inventing local schemas or startup order',
      () => {
        expect(
          LOGRES_GLOBAL_3024_RUNTIME_UNRESOLVED,
        ).toEqual(
          expect.arrayContaining([
            'exact serialized file names and on-disk JSON schemas for every LocalStorageUserDataCategory',
            'exact startup call order among AppDelegate, lfs::application, and GameInformation beyond the exported ownership surfaces',
          ]),
        )
      },
    )
  },
)
