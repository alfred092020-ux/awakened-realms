import {
  execFileSync,
} from 'node:child_process'

import {
  describe,
  expect,
  it,
} from 'vitest'

import {
  LOGRES_FIELD_HUD_LAYOUT_EVIDENCE,
} from '../src/game/logres/tutorial/LogresFieldHudLayoutEvidence'

describe(
  'Logres Global field HUD layout evidence',
  () => {
    it(
      'locks the recovered Global HUD source hashes',
      () => {
        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .source.packageSha256,
        ).toBe(
          'd4fe09e50c8f8fa6cb560ea4ef5348c9092a41fff03f17e316a982f10cc6316a',
        )

        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .source.fieldFooterSha256,
        ).toBe(
          'e15f4433dfbc2be6118a6f6564ecd72c6b1527fa0117a4f473eba1057ade3b2f',
        )
      },
    )

    it(
      'records the original footer bar coordinates and bottom constraint',
      () => {
        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .footerBar.rawPosition,
        ).toEqual({
          x: 360,
          y: 76,
        })

        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .footerBar.sliceSize,
        ).toEqual({
          width: 720,
          height: 100,
        })

        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .footerBar.anchorStyles.bottom,
        ).toBe(45)
      },
    )

    it(
      'records the original menu anchor constraints without inventing a screen transform',
      () => {
        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .menuButton.anchorStyles,
        ).toEqual({
          anchors: [
            'lfs.gui.kVerticalCenter',
            'lfs.gui.kRight',
          ],
          bottom: 0,
          right: 88,
        })

        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .menuNormalImage.anchorStyles,
        ).toEqual({
          bottom: 35,
          left: 88,
        })

        expect(
          LOGRES_FIELD_HUD_LAYOUT_EVIDENCE
            .unresolved.runtimeScreenTransform,
        ).toBe('UNRESOLVED')
      },
    )

    it(
      'passes the standalone inspector self-test without private assets',
      () => {
        const output =
          execFileSync(
            'python3',
            [
              '-B',
              'scripts/logres/inspect_global_field_hud_layout.py',
              '--self-test',
            ],
            {
              encoding:
                'utf8',
            },
          )

        expect(output)
          .toContain(
            'Logres Global field HUD layout inspector self-test: PASS',
          )
      },
    )
  },
)
