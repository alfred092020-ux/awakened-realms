import { loadLogresRendererProofTerrain } from './LogresRendererProofTerrain'
import { buildLogresTerrainMeshData, LOGRES_RENDERER_PROOF_ATLAS_SIZE } from './LogresTerrainMeshData'
import { createTerrainProofRenderer } from './LogresTerrainProofRenderer'

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`Private proof texture unavailable: ${url}`))
    image.src = url
  })
}

/** Opt-in diagnostic entry. It must never be used as the tutorial destination. */
export async function showLogresRendererProof(container: HTMLElement): Promise<void> {
  container.style.cssText = 'width:100%;height:100%;display:flex;flex-direction:column;color:#eee;background:#10131a;font:14px sans-serif'
  const panel = document.createElement('div')
  panel.style.cssText = 'padding:12px;flex:none;line-height:1.5'
  panel.innerHTML = `<strong>001_000_00002 — RENDERER PROOF ONLY</strong>
    <div>Not the tutorial map. Static original geometry; diagnostic bounds-fit view, Y up, CHIP then OBJ, no depth test.</div>
    <div>Camera, depth order, UV origin and input alpha convention remain unresolved.</div>
    <label>UV origin <select id="proof-uv"><option value="top">Top left</option><option value="bottom">Bottom left</option></select></label>
    <label>Layer <select id="proof-layer"><option value="both">Both</option><option value="chip">CHIP</option><option value="obj">OBJ</option></select></label>
    <button id="proof-reset">Fit map</button> Drag to pan; wheel to zoom. <a href="/">Return to title</a>`
  const status = document.createElement('div')
  status.setAttribute('role', 'status'); status.dataset.proofStatus = 'loading'
  status.textContent = 'Loading private map and atlases…'; panel.append(status)
  const canvas = document.createElement('canvas')
  canvas.style.cssText = 'width:100%;min-height:0;flex:1;display:block;touch-action:none'
  canvas.setAttribute('aria-label', 'Static authentic terrain renderer proof')
  container.replaceChildren(panel, canvas)
  let dispose: (() => void) | undefined
  try {
    const proof = await loadLogresRendererProofTerrain()
    const [chip, obj] = await Promise.all([loadImage(proof.textures.chipPng), loadImage(proof.textures.objPng)])
    for (const [kind, image] of Object.entries({ chip, obj })) {
      const size = LOGRES_RENDERER_PROOF_ATLAS_SIZE[kind as 'chip' | 'obj']
      if (image.naturalWidth !== size.width || image.naturalHeight !== size.height) throw new Error(`${kind} atlas dimensions do not match proof evidence`)
    }
    const mesh = buildLogresTerrainMeshData(proof.terrain, { origin: 'top-left' })
    const renderer = createTerrainProofRenderer(canvas, mesh, { chip, obj })
    dispose = renderer.dispose
    const uv = panel.querySelector<HTMLSelectElement>('#proof-uv')!
    const layer = panel.querySelector<HTMLSelectElement>('#proof-layer')!
    let zoom = 1, panX = 0, panY = 0, fit = 1
    const fail = (error: unknown) => {
      status.dataset.proofStatus = 'error'; status.textContent = `Renderer proof unavailable: ${error instanceof Error ? error.message : String(error)}`
    }
    const draw = () => {
      try {
        canvas.width = Math.max(1, Math.round(canvas.clientWidth))
        canvas.height = Math.max(1, Math.round(canvas.clientHeight))
        fit = renderer.render(uv.value === 'bottom', layer.value as 'both' | 'chip' | 'obj', zoom, panX, panY)
        status.dataset.proofStatus = 'ready'
        status.textContent = `${proof.map.gridCount} grids · ${proof.terrain.chipCount} CHIP · ${proof.terrain.objectCount} OBJ · ${renderer.triangleCount} triangles. ${proof.terrain.animatedObjectCount} animated objects omitted; UV pose 0 only.`
      } catch (error) { fail(error) }
    }
    uv.onchange = draw; layer.onchange = draw
    panel.querySelector<HTMLButtonElement>('#proof-reset')!.onclick = () => { zoom = 1; panX = 0; panY = 0; draw() }
    canvas.onwheel = event => { event.preventDefault(); zoom = Math.max(0.25, Math.min(32, zoom * Math.exp(-event.deltaY * 0.001))); draw() }
    let drag: { id: number; x: number; y: number } | undefined
    canvas.onpointerdown = event => { drag = { id: event.pointerId, x: event.clientX, y: event.clientY }; canvas.setPointerCapture(event.pointerId) }
    canvas.onpointermove = event => {
      if (!drag || drag.id !== event.pointerId) return
      panX -= (event.clientX - drag.x) / fit; panY += (event.clientY - drag.y) / fit
      drag.x = event.clientX; drag.y = event.clientY; draw()
    }
    canvas.onpointerup = canvas.onpointercancel = () => { drag = undefined }
    canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); fail(new Error('WebGL context lost; reload this proof view')) })
    const resize = new ResizeObserver(draw); resize.observe(canvas)
    window.addEventListener('pagehide', () => { resize.disconnect(); renderer.dispose() }, { once: true })
    draw()
  } catch (error) {
    dispose?.()
    status.dataset.proofStatus = 'error'
    status.textContent = `Renderer proof unavailable: ${error instanceof Error ? error.message : String(error)}`
  }
}
