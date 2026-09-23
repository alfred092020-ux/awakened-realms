import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
  LOGRES_TUTORIAL_GREEN_JELL_PRESENTATION,
  LOGRES_TUTORIAL_POINTER_OFFSET,
  LOGRES_TUTORIAL_POINTER_PRESENTATION,
} from '../src/game/logres/field/LogresFieldActorPresentation'

describe(
  'Logres tutorial field actor presentation',
  () => {
    it(
      'keeps Green Jell current-JP art separate from unresolved Global internal identity',
      () => {
        expect(
          LOGRES_TUTORIAL_GREEN_JELL_PRESENTATION,
        ).toEqual({
          currentJpResourceFamily:
            'enm_001_000_000',

          source:
            'CONFIRMED_CURRENT_JP_NATIVE_SOURCE_BYTES',

          globalBehavior:
            'CONFIRMED_GLOBAL_GREEN_JELL_TUTORIAL',

          historicalGlobalInternalId:
            'UNRESOLVED',

          globalVisualApplication:
            'SUPPORTED_INFERENCE',
        })
      },
    )

    it(
      'labels tutorial hand behavior separately from artwork provenance and placement',
      () => {
        expect(
          LOGRES_TUTORIAL_POINTER_PRESENTATION,
        ).toEqual({
          source:
            'CONFIRMED_CURRENT_JP_NATIVE_SOURCE_BYTES',

          globalBehavior:
            'CONFIRMED_GLOBAL_VIDEO_HAND_PROMPT',

          globalArtworkApplication:
            'SUPPORTED_INFERENCE',

          placement:
            'RECONSTRUCTED',
        })

        expect(
          LOGRES_TUTORIAL_POINTER_OFFSET
            .placement,
        ).toBe(
          'RECONSTRUCTED',
        )
      },
    )

    it(
      'locks the four-frame current-JP idle presentation',
      () => {
        expect(
          LOGRES_TUTORIAL_GREEN_JELL_IDLE_ANIMATION,
        ).toEqual({
          frameCount:
            4,

          frameRate:
            6,

          repeat:
            -1,
        })
      },
    )

    it(
      'passes the hydrator synthetic self-test without proprietary files',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/hydrate_tutorial_pointer.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        expect(
          output,
        ).toContain(
          'Logres tutorial-field presentation hydrator self-test: PASS',
        )
      },
    )
  },
)
