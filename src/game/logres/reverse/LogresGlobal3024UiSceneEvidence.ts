export const LOGRES_GLOBAL_3024_UI_SCENE_PROVENANCE =
  'CONFIRMED_ORIGINAL_GLOBAL_3_0_24_SYMBOL_AND_PACKAGED_UI_SURFACE' as const

export const LOGRES_GLOBAL_3024_UI_SCENE_SOURCE =
  Object.freeze({
    client: 'Global 3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    evidenceArtifactSha256:
      '6e7c5e1ffd533acc52d74fbd967546103054d26651dd2ed86082db2e3be82351',
  } as const)

export const LOGRES_GLOBAL_3024_UI_SCENE_COUNTS =
  Object.freeze({
    releaseScenes: Object.freeze({ classes: 14, methods: 222 }),
    allSceneClasses: Object.freeze({ classes: 25, methods: 312 }),
    windowClasses: Object.freeze({ classes: 338, methods: 2712 }),
    hudUiClasses: Object.freeze({ classes: 101, methods: 1213 }),
    skitTelopClasses: Object.freeze({ classes: 39, methods: 265 }),
    flashClasses: Object.freeze({ classes: 48, methods: 332 }),
    inputClasses: Object.freeze({ classes: 34, methods: 306 }),
    packagedUiMembers: 399,
    packagedUiPackages: 19,
    lflaFiles: 15,
    lflaResources: 93,
    lflaSymbols: 112,
  } as const)

export const LOGRES_GLOBAL_3024_RELEASE_SCENES =
  Object.freeze([
    'ReleaseScene_AccountLogIn',
    'ReleaseScene_Battle',
    'ReleaseScene_CharacterLogin',
    'ReleaseScene_CharcterMake',
    'ReleaseScene_Entrance',
    'ReleaseScene_GameEntry',
    'ReleaseScene_GameField',
    'ReleaseScene_GetHostEntry',
    'ReleaseScene_HostSelector',
    'ReleaseScene_Loading',
    'ReleaseScene_Maintenance',
    'ReleaseScene_Splash',
    'ReleaseScene_Title',
    'ReleaseScene_WorldSelector',
  ] as const)

export const LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE =
  Object.freeze({
    sceneLifecycle: Object.freeze([
      'onInitializeStart',
      'onInitializeEnd',
      'onFadeInStart',
      'onFadeInEnd',
      'onEnter',
      'onExit',
      'onFinalizeStart',
      'onFinalizeEnd',
    ] as const),
    sceneManager: Object.freeze([
      'changeScene',
      'getCurrentScene',
      'createBattleSceneHub',
      'closeBattleSceneHub',
      'registerKeypadEventListener',
      'unregisterKeypadEventListener',
    ] as const),
    windowManager: Object.freeze([
      'addWindow',
      'removeWindow',
      'closeWindow',
      'bringToFront',
      'bringToBack',
      'reorderWindow',
      'linkToRender',
      'unlinkToRender',
      'terminateAllWindow',
      'terminateAllWindowSync',
    ] as const),
    input: Object.freeze([
      'KeypadEventDispatcher',
      'GestureEventLayer',
      'field::FieldInputDelegate',
      'gui::TextInputAndroid',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_SKIT_ACTIONS =
  Object.freeze([
    'PopImage',
    'MovImage',
    'DelImage',
    'PopSprite',
    'PopText',
    'DelText',
    'PopEffect',
    'SyncEffect',
    'PlayBGM',
    'StopBGM',
    'PlaySE',
    'StopSE',
    'WaitClick',
    'WaitTime',
    'EventStart',
    'EventFinish',
  ] as const)

export const LOGRES_GLOBAL_3024_FLASH_PIPELINE =
  Object.freeze({
    runtime: Object.freeze([
      'FlashResource',
      'FlashPlayer',
      'FlashSequencer',
      'FlashRenderer',
      'flash::Engine',
    ] as const),
    packagedMemberTypes: Object.freeze({
      lua: 21,
      png: 193,
      dds: 155,
      json: 13,
      bss: 2,
      lfla: 15,
    } as const),
    majorPackages: Object.freeze([
      'gui__common_base.mbn',
      'gui__title.mbn',
      'gui__title__effect__png.mbn',
      'gui__title__patchCharacter__png.mbn',
      'gui_CN__share.mbn',
      'gui__characreate.mbn',
      'gui__title__effect.mbn',
      'gui__title__image9Slice.mbn',
      'gui__warning.mbn',
    ] as const),
  } as const)

export const LOGRES_GLOBAL_3024_UI_SCENE_CONCLUSIONS =
  Object.freeze([
    'ReleaseScene is lifecycle-driven over Scene and SceneManager with explicit initialize, fade, enter/exit and finalize phases.',
    'gui::WindowManager centralizes window ownership, z-order, render linking, keypad registration and typed window creation/closure.',
    'Field/menu input adapters feed shared keypad, gesture and Android text-input infrastructure.',
    'Skit presentation is command/action driven with image, sprite, text, effect, audio, timing and click synchronization primitives.',
    'Flash/LFLA presentation uses FlashResource, FlashPlayer, FlashSequencer and FlashRenderer.',
  ] as const)

export const LOGRES_GLOBAL_3024_UI_SCENE_UNRESOLVED =
  Object.freeze([
    'Exact pixel placement for every runtime-created window is not derivable from native symbol names alone.',
    'Historical hosted web/server text used by some screens is absent from the APK.',
    'Exact per-frame rendering of every Flash/Skit asset requires runtime replay beyond static symbol recovery.',
  ] as const)
