import type {
  LogresEvidenceLabel,
} from './LogresTutorialVideoEvidence'

export const LOGRES_TUTORIAL_HUD_DESIGN_SIZE =
  Object.freeze({
    width:
      720,
    height:
      1280,
  })

export interface LogresTutorialHudAssetEvidence {
  id: string
  sourceMember: string
  sourceEntry: string
  sourceSha256: string
  width: number
  height: number
  runtimeUrl: string
  sourceLabel: LogresEvidenceLabel
  tutorialSelectionLabel:
    LogresEvidenceLabel
  selectedForCapturedTutorial:
    boolean
  basis: string
}

export const LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE =
  Object.freeze({
    parameterBar:
      Object.freeze({
        id:
          'tutorial-parameter-bar',
        sourceMember:
          'files/cache/patch/gui/HUD.mbn',
        sourceEntry:
          'field_parameter.dds',
        sourceSha256:
          '3c3ce959ddadba86552c3ee92481f4f7a4d9b4b47a820245c1c3d271a5645e23',
        width:
          410,
        height:
          66,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/hud/field_parameter.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'CONFIRMED ORIGINAL' as const,
        selectedForCapturedTutorial:
          true,
        basis:
          'Recovered Global source bytes and direct visual match to the user-supplied original tutorial HUD frame.',
      } satisfies
        LogresTutorialHudAssetEvidence),

    parameterBarLaterVariant:
      Object.freeze({
        id:
          'later-parameter-bar-variant',
        sourceMember:
          'files/cache/patch/gui/HUD.mbn',
        sourceEntry:
          'field_parameter02.astc',
        sourceSha256:
          'dc38a9fcd26fbe9eb2e672b8f8313107aa89cf8168b41562b969a4d6e6ff5fd8',
        width:
          410,
        height:
          66,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/hud/field_parameter02.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'SUPPORTED INFERENCE' as const,
        selectedForCapturedTutorial:
          false,
        basis:
          'Authentic recovered Global source, but its visual structure does not match the captured tutorial top HUD.',
      } satisfies
        LogresTutorialHudAssetEvidence),

    questStartText:
      Object.freeze({
        id:
          'tutorial-quest-start-text',
        sourceMember:
          'files/cache/patch/motion/telop/png.mbn',
        sourceEntry:
          'quest_start.dds',
        sourceSha256:
          'd4c99f0a551ae53fd1fc9c5c4fd887f49db6eb99fbb8013c70155cbc6d279053',
        width:
          320,
        height:
          64,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/telop/quest_start.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'CONFIRMED ORIGINAL' as const,
        selectedForCapturedTutorial:
          true,
        basis:
          'Recovered Global source bytes and direct visual match to the user-supplied original tutorial quest-start frame.',
      } satisfies
        LogresTutorialHudAssetEvidence),

    questStartBackground:
      Object.freeze({
        id:
          'tutorial-quest-start-background',
        sourceMember:
          'files/cache/patch/motion/telop/png.mbn',
        sourceEntry:
          'quest_bg00.dds',
        sourceSha256:
          '46941e2c47398422acfbfea10603bce20c49b932da0923c4eb9940e0c39cff83',
        width:
          472,
        height:
          110,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/telop/quest_bg00.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'CONFIRMED ORIGINAL' as const,
        selectedForCapturedTutorial:
          true,
        basis:
          'Recovered Global source bytes and direct visual match to the user-supplied original tutorial quest-start scroll.',
      } satisfies
        LogresTutorialHudAssetEvidence),

    fieldUnderbar:
      Object.freeze({
        id:
          'field-underbar',
        sourceMember:
          'files/cache/patch/gui/HUD.mbn',
        sourceEntry:
          'field_underbar.dds',
        sourceSha256:
          '4f5c3c244ee73929799a609322e8220bf97d6eb5af603f6bdce52a9136831b82',
        width:
          720,
        height:
          100,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/hud/field_underbar.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'SUPPORTED INFERENCE' as const,
        selectedForCapturedTutorial:
          false,
        basis:
          'Recovered Global source and original HUD layout resource; exact captured footer-layout variant remains unresolved.',
      } satisfies
        LogresTutorialHudAssetEvidence),

    fieldMenu:
      Object.freeze({
        id:
          'field-menu',
        sourceMember:
          'files/cache/patch/gui/HUD.mbn',
        sourceEntry:
          'field_menu.dds',
        sourceSha256:
          '87f986757d4f490cf24adcad74a2a11fb179552519bbfef647f4cfd53f7ff32d',
        width:
          166,
        height:
          70,
        runtimeUrl:
          '/__logres_ref/global/tutorial-hud/hud/field_menu.png',
        sourceLabel:
          'CONFIRMED ORIGINAL' as const,
        tutorialSelectionLabel:
          'SUPPORTED INFERENCE' as const,
        selectedForCapturedTutorial:
          false,
        basis:
          'Recovered Global source and original HUD layout resource; exact captured footer-layout variant remains unresolved.',
      } satisfies
        LogresTutorialHudAssetEvidence),
  })

export const LOGRES_TUTORIAL_HUD_LAYOUT_EVIDENCE =
  Object.freeze({
    mainHudUnderbarCenter:
      Object.freeze({
        x:
          360,
        y:
          45,
        label:
          'CONFIRMED ORIGINAL' as const,
      }),
    fieldHudFooterUnderbarCenter:
      Object.freeze({
        x:
          360,
        y:
          76,
        label:
          'CONFIRMED ORIGINAL' as const,
      }),
    layoutVariantSelection: {
      label:
        'UNRESOLVED' as const,
    },
  })
