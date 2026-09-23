import {
  loadLogresRendererCandidate,
} from './LogresRendererCandidate'
import {
  buildLogresTerrainMeshData,
} from './LogresTerrainMeshData'
import {
  createTerrainProofRenderer,
} from './LogresTerrainProofRenderer'

function loadImage(
  url: string,
): Promise<HTMLImageElement> {
  return new Promise(
    (
      resolve,
      reject,
    ) => {
      const image =
        new Image()

      image.onload =
        () => resolve(image)

      image.onerror =
        () => reject(
          new Error(
            `Private candidate texture unavailable: ${url}`,
          ),
        )

      image.src =
        url
    },
  )
}
/**
 * Opt-in diagnostic view for recovered map candidates.
 *
 * This view never enters Phaser gameplay and never assigns tutorial identity.
 * The rendered package retains the candidate role supplied by
 * LogresRendererCandidate.
 */
export async function showLogresRendererCandidate(
  container: HTMLElement,
  mapId: string,
): Promise<void> {
  container.style.cssText =
    'width:100%;height:100%;display:flex;flex-direction:column;color:#eee;background:#10131a;font:14px sans-serif'

  const panel =
    document.createElement(
      'div',
    )

  panel.style.cssText =
    'padding:12px;flex:none;line-height:1.5'

  const title =
    document.createElement(
      'strong',
    )

  title.textContent =
    `${mapId} — CANDIDATE MAP DIAGNOSTIC`

  const warning =
    document.createElement(
      'div',
    )

  warning.textContent =
    'CANDIDATE_NOT_IDENTIFIED_TUTORIAL. Static recovered geometry only; this route does not select the gameplay tutorial map.'
  const unresolved =
    document.createElement(
      'div',
    )

  unresolved.textContent =
    'Camera, final depth, animation timing, UV origin and input alpha policy remain diagnostic.'

  const controls =
    document.createElement(
      'div',
    )

  controls.innerHTML =
    '<label>UV origin <select id="candidate-uv"><option value="top">Top left</option><option value="bottom">Bottom left</option></select></label> <label>Layer <select id="candidate-layer"><option value="both">Both</option><option value="chip">CHIP</option><option value="obj">OBJ</option></select></label> <button id="candidate-reset">Fit map</button> Drag to pan; wheel to zoom. <a href="/">Return to title</a>'

  const status =
    document.createElement(
      'div',
    )

  status.setAttribute(
    'role',
    'status',
  )

  status.dataset
    .candidateStatus =
      'loading'

  status.textContent =
    'Loading private candidate map and atlases…'

  panel.append(
    title,
    warning,
    unresolved,
    controls,
    status,
  )
  const canvas =
    document.createElement(
      'canvas',
    )

  canvas.style.cssText =
    'width:100%;min-height:0;flex:1;display:block;touch-action:none'

  canvas.setAttribute(
    'aria-label',
    'Recovered Logres candidate terrain diagnostic',
  )

  container.replaceChildren(
    panel,
    canvas,
  )

  let dispose:
    (() => void) |
    undefined

  try {
    const candidate =
      await loadLogresRendererCandidate(
        mapId,
      )

    const [
      chip,
      obj,
    ] =
      await Promise.all([
        loadImage(
          candidate
            .textures
            .chipPng,
        ),
        loadImage(
          candidate
            .textures
            .objPng,
        ),
      ])
    const mesh =
      buildLogresTerrainMeshData(
        candidate.terrain,
        {
          origin:
            'top-left',
        },
      )

    const renderer =
      createTerrainProofRenderer(
        canvas,
        mesh,
        {
          chip,
          obj,
        },
      )

    dispose =
      renderer.dispose

    const uv =
      panel.querySelector<HTMLSelectElement>(
        '#candidate-uv',
      )!

    const layer =
      panel.querySelector<HTMLSelectElement>(
        '#candidate-layer',
      )!

    let zoom =
      1

    let panX =
      0

    let panY =
      0

    let fit =
      1
    const fail =
      (
        error: unknown,
      ) => {
        status.dataset
          .candidateStatus =
            'error'

        status.textContent =
          `Renderer candidate unavailable: ${error instanceof Error ? error.message : String(error)}`
      }

    const draw =
      () => {
        try {
          canvas.width =
            Math.max(
              1,
              Math.round(
                canvas.clientWidth,
              ),
            )

          canvas.height =
            Math.max(
              1,
              Math.round(
                canvas.clientHeight,
              ),
            )

          fit =
            renderer.render(
              uv.value ===
                'bottom',
              layer.value as
                | 'both'
                | 'chip'
                | 'obj',
              zoom,
              panX,
              panY,
            )
          status.dataset
            .candidateStatus =
              'ready'

          status.textContent =
            `${candidate.gridCount} grids · ${candidate.terrain.chipCount} CHIP · ${candidate.terrain.objectCount} OBJ · ${renderer.triangleCount} triangles. Role: ${candidate.role}. ${candidate.terrain.animatedObjectCount} animated objects omitted; UV pose 0 only.`
        } catch (
          error
        ) {
          fail(
            error,
          )
        }
      }

    uv.onchange =
      draw

    layer.onchange =
      draw

    panel
      .querySelector<HTMLButtonElement>(
        '#candidate-reset',
      )!
      .onclick =
        () => {
          zoom = 1
          panX = 0
          panY = 0
          draw()
        }
    canvas.onwheel =
      (
        event,
      ) => {
        event.preventDefault()

        zoom =
          Math.max(
            0.25,
            Math.min(
              32,
              zoom *
                Math.exp(
                  -event.deltaY *
                    0.001,
                ),
            ),
          )

        draw()
      }

    let drag:
      {
        id: number
        x: number
        y: number
      } |
      undefined

    canvas.onpointerdown =
      (
        event,
      ) => {
        drag = {
          id:
            event.pointerId,
          x:
            event.clientX,
          y:
            event.clientY,
        }

        canvas.setPointerCapture(
          event.pointerId,
        )
      }
    canvas.onpointermove =
      (
        event,
      ) => {
        if (
          !drag ||
          drag.id !==
            event.pointerId
        ) {
          return
        }

        panX -=
          (
            event.clientX -
            drag.x
          ) /
          fit

        panY +=
          (
            event.clientY -
            drag.y
          ) /
          fit

        drag.x =
          event.clientX

        drag.y =
          event.clientY

        draw()
      }

    canvas.onpointerup =
      canvas.onpointercancel =
        () => {
          drag =
            undefined
        }
    canvas.addEventListener(
      'webglcontextlost',
      (
        event,
      ) => {
        event.preventDefault()

        fail(
          new Error(
            'WebGL context lost; reload this candidate view',
          ),
        )
      },
    )

    const resize =
      new ResizeObserver(
        draw,
      )

    resize.observe(
      canvas,
    )

    window.addEventListener(
      'pagehide',
      () => {
        resize.disconnect()
        renderer.dispose()
      },
      {
        once:
          true,
      },
    )

    draw()
  } catch (
    error
  ) {
    dispose?.()

    status.dataset
      .candidateStatus =
        'error'

    status.textContent =
      `Renderer candidate unavailable: ${error instanceof Error ? error.message : String(error)}`
  }
}
