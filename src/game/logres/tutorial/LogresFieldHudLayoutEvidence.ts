export type LogresFieldHudLayoutEvidenceLabel =
  | 'CONFIRMED ORIGINAL'
  | 'UNRESOLVED'

export const LOGRES_FIELD_HUD_LAYOUT_EVIDENCE =
  Object.freeze({
    source: Object.freeze({
      packageMember:
        'files/cache/patch/gui/HUD.mbn',
      packageSha256:
        'd4fe09e50c8f8fa6cb560ea4ef5348c9092a41fff03f17e316a982f10cc6316a',
      mainHudEntry:
        'MainHUD.lua',
      mainHudSha256:
        'b1252039f5f64653578345990d977ddcfa62dd38fe9c8166befedcd78d0d3dc4',
      fieldFooterEntry:
        'field_hud_footer.lua',
      fieldFooterSha256:
        'e15f4433dfbc2be6118a6f6564ecd72c6b1527fa0117a4f473eba1057ade3b2f',
      evidence:
        'CONFIRMED ORIGINAL' as LogresFieldHudLayoutEvidenceLabel,
    }),

    fieldFooterRoot: Object.freeze({
      contentSize: Object.freeze({
        width: 720,
        height: 1104,
      }),
      anchor: Object.freeze({
        x: 0.5,
        y: 1,
      }),
      evidence:
        'CONFIRMED ORIGINAL' as LogresFieldHudLayoutEvidenceLabel,
    }),

    footerBar: Object.freeze({
      resource:
        'gui/HUD/field_underbar.png',
      sliceSize: Object.freeze({
        width: 720,
        height: 100,
      }),
      rawPosition: Object.freeze({
        x: 360,
        y: 76,
      }),
      anchor: Object.freeze({
        x: 0.5,
        y: 0.5,
      }),
      anchorStyles: Object.freeze({
        anchors: Object.freeze([
          'lfs.gui.kBottom',
          'lfs.gui.kHorizontalCenter',
        ]),
        bottom: 45,
      }),
      evidence:
        'CONFIRMED ORIGINAL' as LogresFieldHudLayoutEvidenceLabel,
    }),

    menuButton: Object.freeze({
      name:
        'menu',
      anchorStyles: Object.freeze({
        anchors: Object.freeze([
          'lfs.gui.kVerticalCenter',
          'lfs.gui.kRight',
        ]),
        bottom: 0,
        right: 88,
      }),
      evidence:
        'CONFIRMED ORIGINAL' as LogresFieldHudLayoutEvidenceLabel,
    }),

    menuNormalImage: Object.freeze({
      resource:
        'gui/HUD/field_menu.png',
      rawPosition: Object.freeze({
        x: 0,
        y: 0,
      }),
      anchorStyles: Object.freeze({
        bottom: 35,
        left: 88,
      }),
      evidence:
        'CONFIRMED ORIGINAL' as LogresFieldHudLayoutEvidenceLabel,
    }),

    unresolved: Object.freeze({
      runtimeScreenTransform:
        'UNRESOLVED' as LogresFieldHudLayoutEvidenceLabel,
      historicalFooterVariantSelection:
        'UNRESOLVED' as LogresFieldHudLayoutEvidenceLabel,
      note:
        'Raw Lua coordinates and anchor constraints are confirmed original. Mapping those constraints into the reconstructed Phaser viewport remains a separate runtime decision.',
    }),
  })
