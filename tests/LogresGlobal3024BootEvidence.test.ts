import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_GLOBAL_3024_BOOT_SOURCE,
  LOGRES_GLOBAL_3024_BOOT_UNRESOLVED,
  LOGRES_GLOBAL_3024_FIRST_RUN_ORDER,
  LOGRES_GLOBAL_3024_PERMANENT_REGISTRATION,
  LOGRES_GLOBAL_3024_STARTER_CHARACTER,
  LOGRES_GLOBAL_3024_TERMS_GATE,
  LOGRES_GLOBAL_3024_TITLE_LAYOUT,
  LOGRES_GLOBAL_3024_WORLD_SELECTION,
} from '../src/game/logres/onboarding/LogresGlobal3024BootEvidence'

describe(
  'Global 3.0.24 boot/onboarding evidence',
  () => {
    it(
      'anchors boot evidence to the original Global client and launch video',
      () => {
        expect(
          LOGRES_GLOBAL_3024_BOOT_SOURCE,
        ).toMatchObject({
          clientVersion: '3.0.24',
          libgameArm64Sha256:
            'bf777cfa413b95627152246e9048af5c5fbc9c53e3c49141421360d6e86c814f',
          launchVideoSha256:
            '488e4564622d708f8bd5ff433fb9307ee1eb50f16832d3921242bb5ff3be7d6f',
        })

        expect(
          LOGRES_GLOBAL_3024_TITLE_LAYOUT,
        ).toMatchObject({
          backgroundCenter: [360, 640],
          logoCenter: [360, 367],
          startButtonTopOriginPosition:
            [360, 1080],
        })
      },
    )

    it(
      'keeps the Terms agreement as a WebView/auth boundary rather than fabricated legal copy',
      () => {
        expect(
          LOGRES_GLOBAL_3024_TERMS_GATE,
        ).toEqual(
          expect.objectContaining({
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
          }),
        )
      },
    )

    it(
      'does not force World Select into the observed first-run path',
      () => {
        expect(
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .nativeScene,
        ).toBe(
          'ReleaseScene_WorldSelector',
        )

        expect(
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .authWorldFunctions,
        ).toEqual(
          expect.arrayContaining([
            'IsValidWorldID',
            'GetSavedWorldID',
            'GetDefaultWorldID',
            'RequestWorldID',
          ]),
        )

        expect(
          LOGRES_GLOBAL_3024_WORLD_SELECTION
            .launchVideoObservation,
        ).toBe(
          'NO_WORLD_SELECTOR_BETWEEN_TERMS_AND_GENDER',
        )

        expect(
          LOGRES_GLOBAL_3024_FIRST_RUN_ORDER,
        ).not.toContain(
          'WORLD_SELECT',
        )
      },
    )

    it(
      'preserves temporary gender-only creation before the tutorial field',
      () => {
        expect(
          LOGRES_GLOBAL_3024_STARTER_CHARACTER,
        ).toMatchObject({
          firstCreationStep:
            'SELECT_GENDER_ONLY',
          temporaryName:
            'Novice',
          initialJob:
            'Fighter',
          initialLevel: 1,
          observedEp: {
            current: 0,
            cap: 5,
          },
          firstField:
            'Millennium Tree',
          observedRoom: 2,
        })
      },
    )

    it(
      'keeps permanent name/hair/face registration later in Hunter Guild progression',
      () => {
        expect(
          LOGRES_GLOBAL_3024_PERMANENT_REGISTRATION,
        ).toMatchObject({
          timing:
            'LATER_HUNTER_GUILD_PROGRESSION',
          controls: [
            'Enter your name',
            'Hair',
            'Face',
          ],
          earlyFullCharacterMake:
            false,
          exactQuestOrServerTrigger:
            'UNRESOLVED',
        })

        expect(
          LOGRES_GLOBAL_3024_BOOT_UNRESOLVED,
        ).toEqual(
          expect.arrayContaining([
            'exact normal-production condition that shows World Selector',
            'exact Global quest/server trigger for permanent Hunter registration',
          ]),
        )
      },
    )
  },
)
