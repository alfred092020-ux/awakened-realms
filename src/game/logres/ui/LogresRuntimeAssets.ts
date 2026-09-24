import type Phaser from 'phaser'

export const LOGRES_RUNTIME_REVISION =
  'apk-v4-demo01-20260923'

export function logresRuntimeUrl(
  path: string,
) {
  const separator =
    path.includes('?')
      ? '&'
      : '?'

  return (
    path +
    separator +
    'runtime=' +
    encodeURIComponent(
      LOGRES_RUNTIME_REVISION,
    )
  )
}

export const LOGRES_ASSETS = {
  titleBackground: {
    key:
      'logres-global-title-background',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/title_back.dds.png',
      ),
  },

  titleLogo: {
    key:
      'logres-global-title-logo',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/effect/png/logo00.png',
      ),
  },

  titleBase: {
    key:
      'logres-global-title-base',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/title_base01.dds.png',
      ),
  },

  titleStart: {
    key:
      'logres-global-title-start',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/title_ok.png',
      ),
  },

  titleNext: {
    key:
      'logres-global-title-next',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/title_next.png',
      ),
  },

  worldSelect: {
    key:
      'logres-global-world-select',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select01.png',
      ),
  },

  worldSelect02: {
    key:
      'logres-global-world-select-02',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select02.png',
      ),
  },

  worldSelect03: {
    key:
      'logres-global-world-select-03',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select03.png',
      ),
  },

  worldSelect04: {
    key:
      'logres-global-world-select-04',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select04.png',
      ),
  },

  worldSelect05: {
    key:
      'logres-global-world-select-05',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select05.png',
      ),
  },

  worldSelect06: {
    key:
      'logres-global-world-select-06',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select06.png',
      ),
  },

  worldSelect07: {
    key:
      'logres-global-world-select-07',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/title/world_select07.png',
      ),
  },

  skillBase: {
    key:
      'logres-global-skill-base',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/common_base/skill_base.png',
      ),
  },

  battleWeaponCover: {
    key:
      'logres-global-battle-weapon-cover',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/Battle/bat_select_parts01.dds.png',
      ),
  },

  tutorialParameterBar: {
    key:
      'logres-global-tutorial-parameter-bar',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/tutorial-hud/hud/field_parameter.png',
      ),
  },

  tutorialQuestStartText: {
    key:
      'logres-global-tutorial-quest-start-text',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/tutorial-hud/telop/quest_start.png',
      ),
  },

  tutorialQuestStartBackground: {
    key:
      'logres-global-tutorial-quest-start-background',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/tutorial-hud/telop/quest_bg00.png',
      ),
  },

  tutorialFieldUnderbar: {
    key:
      'logres-global-tutorial-field-underbar',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/tutorial-hud/hud/field_underbar.png',
      ),
  },

  tutorialFieldMenu: {
    key:
      'logres-global-tutorial-field-menu',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/tutorial-hud/hud/field_menu.png',
      ),
  },

  equipmentSkillBase: {
    key:
      'logres-global-equipment-skill-base',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/common_base/soubi01_02_skillbase.png',
      ),
  },

  characterMan: {
    key:
      'logres-global-character-man',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_man.dds.png',
      ),
  },

  characterWoman: {
    key:
      'logres-global-character-woman',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_woman.dds.png',
      ),
  },

  characterChangeMan: {
    key:
      'logres-global-character-change-man',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_change01.dds.png',
      ),
  },

  characterChangeWoman: {
    key:
      'logres-global-character-change-woman',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_change02.dds.png',
      ),
  },

  characterTitleBase: {
    key:
      'logres-global-character-title-base',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/slice/charaselect_titlebase.dds.png',
      ),
  },

  characterTitle: {
    key:
      'logres-global-character-title',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_title01.png',
      ),
  },

  characterOk: {
    key:
      'logres-global-character-ok',

    url:
      logresRuntimeUrl(
        '/__logres_ref/global/gui/characreate/charaselect_ok.png',
      ),
  },
} as const

type DiagnosticLoader =
  Phaser.Loader.LoaderPlugin & {
    __logresRuntimeDiagnostics?:
      boolean
  }

function installLogresRuntimeDiagnostics(
  scene: Phaser.Scene,
) {
  const loader =
    scene.load as DiagnosticLoader

  if (
    loader.__logresRuntimeDiagnostics
  ) {
    return
  }

  loader.__logresRuntimeDiagnostics =
    true

  loader.on(
    'loaderror',
    (file: Phaser.Loader.File) => {
      const message = [
        'LOGRES RUNTIME LOAD FAILED',
        'scene=' + scene.scene.key,
        'key=' + String(file.key),
        'src=' + String(file.src),
        'origin=' + window.location.origin,
      ].join('\n')

      console.error(message)

      let overlay =
        document.getElementById(
          'logres-runtime-load-error',
        )

      if (!overlay) {
        overlay =
          document.createElement('pre')
        overlay.id =
          'logres-runtime-load-error'
        overlay.style.position = 'fixed'
        overlay.style.zIndex = '2147483647'
        overlay.style.left = '8px'
        overlay.style.right = '8px'
        overlay.style.top = '80px'
        overlay.style.maxHeight = '45vh'
        overlay.style.overflow = 'auto'
        overlay.style.margin = '0'
        overlay.style.padding = '10px'
        overlay.style.background =
          'rgba(80,0,0,0.94)'
        overlay.style.color = '#ffffff'
        overlay.style.font =
          '12px monospace'
        overlay.style.whiteSpace =
          'pre-wrap'
        document.body.appendChild(overlay)
      }

      overlay.textContent =
        (
          overlay.textContent
            ? overlay.textContent + '\n\n'
            : ''
        ) +
        message
    },
  )
}

export function preloadLogresAssets(
  scene: Phaser.Scene,
) {
  installLogresRuntimeDiagnostics(
    scene,
  )

  for (
    const asset of
    Object.values(
      LOGRES_ASSETS,
    )
  ) {
    if (
      scene.textures.exists(
        asset.key,
      )
    ) {
      continue
    }

    scene.load.image(
      asset.key,
      asset.url,
    )
  }
}
