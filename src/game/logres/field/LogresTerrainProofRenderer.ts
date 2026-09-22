import type { LogresTerrainMeshData, LogresTerrainMeshGroup } from './LogresTerrainMeshData'

/** Diagnostic framing only; original camera, Z ordering and animation remain unresolved. */
export function terrainProofBounds(groups: readonly LogresTerrainMeshGroup[]) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const group of groups) {
    if (group.vertices.length % 2) throw new Error('Terrain XY pairs are incomplete')
    for (let i = 0; i < group.vertices.length; i += 2) {
      const x = group.vertices[i]!, y = group.vertices[i + 1]!
      if (!Number.isFinite(x) || !Number.isFinite(y)) throw new Error('Terrain position must be finite')
      minX = Math.min(minX, x); maxX = Math.max(maxX, x)
      minY = Math.min(minY, y); maxY = Math.max(maxY, y)
    }
  }
  if (minX === Infinity) throw new Error('No terrain vertices')
  return { centerX: (minX + maxX) / 2, centerY: (minY + maxY) / 2, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) }
}

/** Expand indices so WebGL1 can draw arbitrarily large maps without uint32 index support. */
export function expandTerrainProofTriangles(group: LogresTerrainMeshGroup): Float32Array {
  if (group.vertices.length % 2 || group.uvs.length !== group.vertices.length || group.indices.length % 3) {
    throw new Error('Invalid terrain position/UV/triangle counts')
  }
  const data = new Float32Array(group.indices.length * 4)
  group.indices.forEach((index, offset) => {
    if (!Number.isSafeInteger(index) || index < 0 || index * 2 >= group.vertices.length) throw new Error('Invalid terrain index')
    const values = [group.vertices[index * 2]!, group.vertices[index * 2 + 1]!, group.uvs[index * 2]!, group.uvs[index * 2 + 1]!]
    if (!values.every(v => Number.isFinite(v) && Number.isFinite(Math.fround(v)))) throw new Error('Terrain values must be finite float32')
    data.set(values, offset * 4)
  })
  return data
}

/** Standalone diagnostic GL context; never changes Phaser's state or gameplay camera. */
export function createTerrainProofRenderer(
  canvas: HTMLCanvasElement,
  mesh: LogresTerrainMeshData,
  images: { chip: HTMLImageElement; obj: HTMLImageElement },
) {
  const gl = canvas.getContext('webgl', { alpha: false, antialias: false, preserveDrawingBuffer: true })
  if (!gl) throw new Error('WebGL is required for the terrain proof')
  const buffers: WebGLBuffer[] = [], textures: WebGLTexture[] = [], shaders: WebGLShader[] = []
  const program = gl.createProgram()
  if (!program) throw new Error('Unable to allocate terrain program')
  const dispose = () => {
    buffers.forEach(b => gl.deleteBuffer(b)); textures.forEach(t => gl.deleteTexture(t))
    shaders.forEach(s => gl.deleteShader(s)); gl.deleteProgram(program)
  }
  try {
    for (const [type, source] of [
      [gl.VERTEX_SHADER, 'attribute vec2 xy; attribute vec2 uv; uniform vec2 center; uniform vec2 scale; varying vec2 tex; void main(){gl_Position=vec4((xy-center)*scale,0.,1.);tex=uv;}'],
      [gl.FRAGMENT_SHADER, 'precision mediump float; varying vec2 tex; uniform sampler2D atlas; uniform float flipV; void main(){gl_FragColor=texture2D(atlas,vec2(tex.x,mix(tex.y,1.-tex.y,flipV)));}'],
    ] as const) {
      const shader = gl.createShader(type)
      if (!shader) throw new Error('Unable to allocate terrain shader')
      shaders.push(shader); gl.shaderSource(shader, source); gl.compileShader(shader)
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? 'Terrain shader failed')
      gl.attachShader(program, shader)
    }
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program) ?? 'Terrain link failed')
    gl.useProgram(program)
    const groups = [mesh.chip, mesh.obj]
    const bounds = terrainProofBounds(groups)
    const xy = gl.getAttribLocation(program, 'xy'), uv = gl.getAttribLocation(program, 'uv')
    const center = gl.getUniformLocation(program, 'center'), scale = gl.getUniformLocation(program, 'scale')
    const flip = gl.getUniformLocation(program, 'flipV')
    gl.uniform1i(gl.getUniformLocation(program, 'atlas'), 0)
    const counts = groups.map(group => {
      const data = expandTerrainProofTriangles(group)
      const buffer = gl.createBuffer(), texture = gl.createTexture()
      if (buffer) buffers.push(buffer)
      if (texture) textures.push(texture)
      if (!buffer || !texture) throw new Error('Unable to allocate terrain resources')
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW)
      gl.bindTexture(gl.TEXTURE_2D, texture)
      // Preserve hydrated rows/channel values; input alpha convention is not yet proven.
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false)
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false)
      gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE)
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, images[group.texture])
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE)
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST)
      // Diagnostic minification; original MIN policy is not established.
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST)
      return data.length / 4
    })
    gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE)
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA)
    const render = (flipV = false, layer: 'both' | 'chip' | 'obj' = 'both', zoom = 1, panX = 0, panY = 0) => {
      if (gl.isContextLost()) throw new Error('WebGL context lost; reload this proof view')
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.clearColor(0.035, 0.045, 0.06, 1); gl.clear(gl.COLOR_BUFFER_BIT)
      const fit = Math.min(canvas.width / bounds.width, canvas.height / bounds.height) * 0.92 * zoom
      gl.uniform2f(center, bounds.centerX + panX, bounds.centerY + panY)
      gl.uniform2f(scale, 2 * fit / canvas.width, 2 * fit / canvas.height)
      gl.uniform1f(flip, Number(flipV))
      groups.forEach((group, i) => {
        if (layer !== 'both' && layer !== group.texture) return
        gl.bindBuffer(gl.ARRAY_BUFFER, buffers[i]!)
        gl.enableVertexAttribArray(xy); gl.vertexAttribPointer(xy, 2, gl.FLOAT, false, 16, 0)
        gl.enableVertexAttribArray(uv); gl.vertexAttribPointer(uv, 2, gl.FLOAT, false, 16, 8)
        gl.bindTexture(gl.TEXTURE_2D, textures[i]!)
        gl.drawArrays(gl.TRIANGLES, 0, counts[i]!)
      })
      const error = gl.getError()
      if (error !== gl.NO_ERROR) throw new Error(`Terrain WebGL error: ${error}`)
      return fit
    }
    return { render, dispose, triangleCount: counts.reduce((a, b) => a + b, 0) / 3 }
  } catch (error) {
    dispose(); throw error
  }
}
