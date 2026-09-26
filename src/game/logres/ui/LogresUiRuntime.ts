import {
  LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE,
  LOGRES_GLOBAL_3024_UI_SCENE_CONCLUSIONS,
  LOGRES_GLOBAL_3024_UI_SCENE_UNRESOLVED,
} from '../reverse/LogresGlobal3024UiSceneEvidence'
import {
  LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE,
  LOGRES_TUTORIAL_HUD_DESIGN_SIZE,
} from '../tutorial/LogresTutorialHudEvidence'

export type LogresUiSurface =
  | 'FIELD_HUD'
  | 'FIELD_MENU'

export type LogresUiEvidenceLabel =
  | 'CONFIRMED_ORIGINAL'
  | 'SUPPORTED_INFERENCE'
  | 'UNKNOWN'

export interface LogresUiWindowState {
  readonly surface: LogresUiSurface
  readonly zIndex: number
  readonly linkedToRender: boolean
  readonly evidence: LogresUiEvidenceLabel
}

export const LOGRES_UI_RUNTIME_EVIDENCE = Object.freeze({
  designSize: LOGRES_TUTORIAL_HUD_DESIGN_SIZE,
  fieldUnderbarAsset:
    LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.fieldUnderbar,
  fieldMenuAsset:
    LOGRES_TUTORIAL_HUD_ASSET_EVIDENCE.fieldMenu,
  windowManagerOperations:
    LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE.windowManager,
  inputArchitecture:
    LOGRES_GLOBAL_3024_SCENE_ARCHITECTURE.input,
  conclusions:
    LOGRES_GLOBAL_3024_UI_SCENE_CONCLUSIONS,
  unresolved:
    LOGRES_GLOBAL_3024_UI_SCENE_UNRESOLVED,
})

export class LogresUiRuntime {
  private readonly windows: LogresUiWindowState[] = [
    Object.freeze({
      surface: 'FIELD_HUD',
      zIndex: 0,
      linkedToRender: true,
      evidence: 'CONFIRMED_ORIGINAL',
    }),
  ]

  get stack(): readonly LogresUiWindowState[] {
    return this.windows
  }

  get current(): LogresUiWindowState {
    return this.windows[this.windows.length - 1]
  }

  openFieldMenu(): LogresUiWindowState {
    const existing =
      this.windows.find(
        (entry) =>
          entry.surface === 'FIELD_MENU',
      )

    if (existing) {
      this.bringToFront('FIELD_MENU')
      return this.current
    }

    const state =
      Object.freeze({
        surface: 'FIELD_MENU' as const,
        zIndex: this.windows.length,
        linkedToRender: true,
        evidence:
          'SUPPORTED_INFERENCE' as const,
      })

    this.windows.push(state)
    return state
  }

  closeTop(): LogresUiWindowState {
    if (this.windows.length > 1) {
      this.windows.pop()
    }
    return this.current
  }

  bringToFront(
    surface: LogresUiSurface,
  ): LogresUiWindowState {
    const index =
      this.windows.findIndex(
        (entry) =>
          entry.surface === surface,
      )

    if (index < 0) {
      throw new Error(
        `Logres UI surface is not open: ${surface}`,
      )
    }

    const [target] =
      this.windows.splice(index, 1)

    this.windows.push(
      Object.freeze({
        ...target,
        zIndex:
          this.windows.length,
      }),
    )

    return this.current
  }

  terminateAllWindows(): LogresUiWindowState {
    this.windows.splice(1)
    return this.current
  }
}

export interface MountedLogresUiRuntime {
  readonly runtime: LogresUiRuntime
  readonly root: HTMLElement
  render(): void
  destroy(): void
}

function createButton(
  label: string,
  action: string,
): HTMLButtonElement {
  const button =
    document.createElement('button')
  button.type = 'button'
  button.textContent = label
  button.dataset.logresAction = action
  button.style.minWidth = '140px'
  button.style.minHeight = '56px'
  button.style.fontSize = '22px'
  button.style.cursor = 'pointer'
  return button
}

export function mountLogresUiRuntime(
  parent: HTMLElement,
): MountedLogresUiRuntime {
  const runtime =
    new LogresUiRuntime()

  const root =
    document.createElement('section')
  root.dataset.logresUiRuntime = 'mounted'
  root.style.position = 'fixed'
  root.style.inset = '0'
  root.style.zIndex = '2147483000'
  root.style.pointerEvents = 'none'
  root.style.fontFamily = 'sans-serif'

  const render = () => {
    root.replaceChildren()
    root.dataset.logresSurface =
      runtime.current.surface
    root.dataset.logresStack =
      runtime.stack
        .map((entry) => entry.surface)
        .join('>')

    const panel =
      document.createElement('div')
    panel.style.pointerEvents = 'auto'
    panel.style.position = 'absolute'
    panel.style.left = '50%'
    panel.style.transform =
      'translateX(-50%)'
    panel.style.display = 'grid'
    panel.style.justifyItems = 'center'
    panel.style.gap = '12px'

    if (
      runtime.current.surface ===
      'FIELD_HUD'
    ) {
      panel.style.bottom = '0'
      panel.style.width =
        'min(100vw, 720px)'
      panel.style.gap = '0'
      root.dataset.logresFooterVariant =
        'UNRESOLVED'
      root.dataset.logresFooterPlacement =
        'RECONSTRUCTED'

      const footer =
        document.createElement('div')
      footer.style.position = 'relative'
      footer.style.width = '100%'

      const recoveredUnderbar =
        document.createElement('img')
      recoveredUnderbar.alt =
        'Recovered Logres field underbar'
      recoveredUnderbar.src =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldUnderbarAsset.runtimeUrl
      recoveredUnderbar.dataset.logresEvidence =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldUnderbarAsset.sourceLabel
      recoveredUnderbar.width =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldUnderbarAsset.width
      recoveredUnderbar.height =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldUnderbarAsset.height
      recoveredUnderbar.style.display = 'block'
      recoveredUnderbar.style.width = '100%'
      recoveredUnderbar.style.height = 'auto'

      const recoveredMenu =
        document.createElement('img')
      recoveredMenu.alt =
        'Recovered Logres field menu'
      recoveredMenu.src =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldMenuAsset.runtimeUrl
      recoveredMenu.dataset.logresEvidence =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldMenuAsset.sourceLabel
      recoveredMenu.width =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldMenuAsset.width
      recoveredMenu.height =
        LOGRES_UI_RUNTIME_EVIDENCE
          .fieldMenuAsset.height
      recoveredMenu.style.display = 'block'
      recoveredMenu.style.width = '100%'
      recoveredMenu.style.height = 'auto'

      const open =
        document.createElement('button')
      open.type = 'button'
      open.dataset.logresAction =
        'open-field-menu'
      open.setAttribute(
        'aria-label',
        'Open field menu',
      )
      open.style.position = 'absolute'
      open.style.right = '0'
      open.style.bottom = '0'
      open.style.width =
        (
          LOGRES_UI_RUNTIME_EVIDENCE
            .fieldMenuAsset.width /
          LOGRES_UI_RUNTIME_EVIDENCE
            .fieldUnderbarAsset.width *
          100
        ).toFixed(3) + '%'
      open.style.padding = '0'
      open.style.border = '0'
      open.style.background = 'transparent'
      open.style.cursor = 'pointer'
      open.append(recoveredMenu)
      open.addEventListener(
        'click',
        () => {
          runtime.openFieldMenu()
          render()
        },
      )

      footer.append(
        recoveredUnderbar,
        open,
      )
      panel.append(footer)
    } else {
      panel.style.top = '20%'
      panel.style.width = '80%'
      panel.style.maxWidth = '600px'
      panel.style.minHeight = '320px'
      panel.style.padding = '28px'
      panel.style.background =
        'rgba(14, 20, 29, 0.94)'
      panel.style.color = '#fff'
      panel.style.border =
        '2px solid rgba(255,255,255,0.8)'

      const heading =
        document.createElement('h2')
      heading.textContent = 'Field Menu'
      heading.style.margin = '0'

      const evidence =
        document.createElement('p')
      evidence.dataset.logresUiEvidence =
        runtime.current.evidence
      evidence.textContent =
        'Window ownership, ordering, close/back behavior, and the field-menu resource are evidence-backed. Exact historical menu contents remain unresolved.'

      const close =
        createButton(
          'Back',
          'close-window',
        )
      close.addEventListener(
        'click',
        () => {
          runtime.closeTop()
          render()
        },
      )

      panel.append(
        heading,
        evidence,
        close,
      )
    }

    root.append(panel)
  }

  const destroy = () => {
    root.remove()
  }

  parent.append(root)
  render()

  return {
    runtime,
    root,
    render,
    destroy,
  }
}

declare global {
  interface Window {
    __LOGRES_UI_RUNTIME_FACTORY__?: {
      mount(
        parent?: HTMLElement,
      ): MountedLogresUiRuntime
    }
  }
}

if (typeof window !== 'undefined') {
  window.__LOGRES_UI_RUNTIME_FACTORY__ =
    Object.freeze({
      mount(
        parent = document.body,
      ) {
        return mountLogresUiRuntime(
          parent,
        )
      },
    })
}
