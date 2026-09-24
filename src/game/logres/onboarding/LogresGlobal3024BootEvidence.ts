export const LOGRES_GLOBAL_3024_BOOT_SOURCE =
  Object.freeze({
    clientVersion: '3.0.24',
    libgameArm64Sha256:
      'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
    launchVideoSha256:
      '488e4564622d708f8bd5ff433fb9307ee1eb50f16832d3921242bb5ff3be7d6f',
  } as const)

export const LOGRES_GLOBAL_3024_TITLE_LAYOUT =
  Object.freeze({
    backgroundCenter:
      [360, 640] as const,
    logoTopLeft:
      [5, 200] as const,
    logoSize:
      [710, 334] as const,
    logoCenter:
      [360, 367] as const,
    startButtonNativePosition:
      [360, 200] as const,
    startButtonTopOriginPosition:
      [360, 1080] as const,
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
  } as const)

export const LOGRES_GLOBAL_3024_TERMS_GATE =
  Object.freeze({
    launchOrder:
      'START_THEN_TERMS_THEN_GENDER',
    loginFailureCode:
      'E_GMCL_ACCLOGIN_NOT_AGREEMENT',
    agreementScene:
      'AgreementWebView',
    authOperation:
      'agree_to_terms',
    hostEntryField:
      'webViewUrls.terms',
    exactHostedPage:
      'UNRESOLVED',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_3_0_24',
  } as const)

export const LOGRES_GLOBAL_3024_WORLD_SELECTION =
  Object.freeze({
    nativeScene:
      'ReleaseScene_WorldSelector',
    nativeTapHandler:
      'ReleaseScene_WorldSelector::onTapWorldButton(int)',
    authWorldFunctions:
      Object.freeze([
        'SaveWorldID',
        'ResetWorldID',
        'IsValidWorldID',
        'GetSavedWorldID',
        'GetDefaultWorldID',
        'RequestWorldID',
      ] as const),
    skipOption:
      'CommandLineOption::SkipWorldSelect',
    launchVideoObservation:
      'NO_WORLD_SELECTOR_BETWEEN_TERMS_AND_GENDER',
    firstRunRequirement:
      'CONDITIONAL_NOT_CONFIRMED_MANDATORY',
    provenance:
      'NATIVE_SCENE_CONFIRMED_FLOW_CONDITION_SUPPORTED_INFERENCE',
  } as const)

export const LOGRES_GLOBAL_3024_STARTER_CHARACTER =
  Object.freeze({
    firstCreationStep:
      'SELECT_GENDER_ONLY',
    nativeScene:
      'ReleaseScene_CharcterMake',
    createResponse:
      'C_GMCL_CHAR_CREATE_REQ_Response',
    genderControls:
      Object.freeze([
        'CharacterGenderWindow',
        'CharacterGenderSelection',
      ] as const),
    temporaryName:
      'Novice',
    initialJob:
      'Fighter',
    initialLevel: 1,
    observedEp:
      Object.freeze({
        current: 0,
        cap: 5,
      } as const),
    firstField:
      'Millennium Tree',
    observedRoom: 2,
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_LAUNCH_ERA',
  } as const)

export const LOGRES_GLOBAL_3024_PERMANENT_REGISTRATION =
  Object.freeze({
    timing:
      'LATER_HUNTER_GUILD_PROGRESSION',
    observedVideoRange:
      '09:45-10:30',
    controls:
      Object.freeze([
        'Enter your name',
        'Hair',
        'Face',
      ] as const),
    earlyFullCharacterMake:
      false,
    exactQuestOrServerTrigger:
      'UNRESOLVED',
    provenance:
      'CONFIRMED_ORIGINAL_GLOBAL_LAUNCH_ERA',
  } as const)

export const LOGRES_GLOBAL_3024_FIRST_RUN_ORDER =
  Object.freeze([
    'TITLE_START',
    'TERMS_WEBVIEW_GATE',
    'GENDER_SELECTION',
    'TEMPORARY_CHARACTER_CREATE',
    'LOADING_TUTORIAL_CARD',
    'MILLENNIUM_TREE_FIELD',
  ] as const)

export const LOGRES_GLOBAL_3024_BOOT_UNRESOLVED =
  Object.freeze([
    'exact 2017 Terms URL and hosted legal page contents',
    'exact normal-production condition that shows World Selector',
    'exact internal static map ID for the first Millennium Tree field',
    'exact Global quest/server trigger for permanent Hunter registration',
    'exact historical starter body and equipment resource IDs',
  ] as const)
