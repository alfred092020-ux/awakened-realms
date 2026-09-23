import {
  loadLogresRendererCandidate,
  logresRendererCandidateUrls,
  type LoadedLogresRendererCandidate,
} from './LogresRendererCandidate'

import {
  parseLogresMapInfoTable,
} from './LogresMapInfoBinary'

import {
  createLogresFieldMovementSurface,
  type LogresFieldMovementSurface,
} from './LogresFieldNativeLevels'

import {
  buildLogresTerrainMeshData,
  type LogresTerrainMeshData,
} from './LogresTerrainMeshData'

import {
  terrainProofBounds,
} from './LogresTerrainProofRenderer'

import type {
  LogresFieldNavigationTile,
} from './LogresFieldNavigation'

export const LOGRES_PLAYABLE_FIELD_MAP_ID =
  '002_000_00001' as const

export const LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE =
  'SUPPORTED_INFERENCE' as const

export const LOGRES_PLAYABLE_FIELD_RUNTIME_PROVENANCE =
  'RECONSTRUCTED' as const

export const LOGRES_PLAYABLE_FIELD_PROJECTION_EVIDENCE =
  'SUPPORTED_INFERENCE_CURRENT_JP_NATIVE_PLUS_GLOBAL_GEOMETRY' as const

export const LOGRES_FIELD_TILE_SCREEN_STEP_X =
  44 as const

export const LOGRES_FIELD_TILE_SCREEN_STEP_Y =
  22 as const

export interface LogresPlayableFieldRasterTransform {
  width: number
  height: number
  fit: number
  centerX: number
  centerY: number
}

export interface LogresPlayableFieldTilePoint {
  x: number
  y: number
}

export interface LoadedLogresPlayableFieldRuntime {
  provenance:
    typeof LOGRES_PLAYABLE_FIELD_RUNTIME_PROVENANCE

  mapId:
    string

  mapBindingProvenance:
    typeof LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE

  projectionEvidence:
    typeof LOGRES_PLAYABLE_FIELD_PROJECTION_EVIDENCE

  candidate:
    LoadedLogresRendererCandidate

  movement:
    LogresFieldMovementSurface

  mesh:
    LogresTerrainMeshData

  spawn:
    Readonly<LogresFieldNavigationTile>
}

function requirePositiveDimension(
  value: number,
  label: string,
): number {
  if (
    !Number.isFinite(
      value,
    ) ||
    value <= 0
  ) {
    throw new Error(
      `${label} must be a positive finite number`,
    )
  }

  return value
}

async function fetchBinary(
  url: string,
  fetchImpl:
    typeof fetch,
): Promise<Uint8Array> {
  const response =
    await fetchImpl(
      url,
    )

  if (
    !response.ok
  ) {
    throw new Error(
      `Playable field runtime asset unavailable: ${url} (HTTP ${response.status})`,
    )
  }

  return new Uint8Array(
    await response
      .arrayBuffer(),
  )
}

export function logresPlayableFieldInfoUrls(
  mapId:
    string =
      LOGRES_PLAYABLE_FIELD_MAP_ID,
  root =
    '/__logres_ref/renderer-proof',
) {
  const candidate =
    logresRendererCandidateUrls(
      mapId,
      root,
    )

  const base =
    candidate
      .mapBinary
      .slice(
        0,
        candidate
          .mapBinary
          .lastIndexOf(
            '/',
          ),
      )

  return Object.freeze({
    chip:
      `${base}/chip_d.bin`,
    object:
      `${base}/object_d.bin`,
  })
}

/**
 * Tile -> recovered field screen anchor.
 *
 * The 44/22 lattice follows directly from current-JP FieldConstant +
 * Isometric native formulas and is independently visible in repeated Global
 * map primitives. Applying it to the May-2017 Global target is therefore
 * SUPPORTED_INFERENCE, not a claim of recovered Global source code.
 *
 * Movement level contributes one 22 px vertical step. This matches the native
 * grid-size/isometric initializer and recovered Global movement-level model.
 */
export function projectLogresPlayableFieldTile(
  tile:
    Pick<
      LogresFieldNavigationTile,
      | 'col'
      | 'row'
      | 'level'
    >,
): Readonly<LogresPlayableFieldTilePoint> {
  for (
    const [
      value,
      label,
    ]
    of [
      [
        tile.col,
        'Field col',
      ],
      [
        tile.row,
        'Field row',
      ],
      [
        tile.level,
        'Field level',
      ],
    ] as const
  ) {
    if (
      !Number.isSafeInteger(
        value,
      )
    ) {
      throw new Error(
        `${label} must be a safe integer`,
      )
    }
  }

  return Object.freeze({
    x:
      LOGRES_FIELD_TILE_SCREEN_STEP_X *
      (
        tile.col -
        tile.row
      ),

    y:
      -LOGRES_FIELD_TILE_SCREEN_STEP_Y *
      (
        tile.col +
        tile.row +
        1 -
        tile.level
      ),
  })
}

export function createLogresPlayableFieldRasterTransform(
  mesh:
    LogresTerrainMeshData,
  width: number,
  height: number,
): Readonly<LogresPlayableFieldRasterTransform> {
  const canvasWidth =
    requirePositiveDimension(
      width,
      'Field raster width',
    )

  const canvasHeight =
    requirePositiveDimension(
      height,
      'Field raster height',
    )

  const bounds =
    terrainProofBounds([
      mesh.chip,
      mesh.obj,
    ])

  const fit =
    Math.min(
      canvasWidth /
        bounds.width,
      canvasHeight /
        bounds.height,
    ) *
    0.92

  return Object.freeze({
    width:
      canvasWidth,
    height:
      canvasHeight,
    fit,
    centerX:
      bounds.centerX,
    centerY:
      bounds.centerY,
  })
}

export function projectLogresPlayableFieldTileToRaster(
  tile:
    Pick<
      LogresFieldNavigationTile,
      | 'col'
      | 'row'
      | 'level'
    >,
  transform:
    LogresPlayableFieldRasterTransform,
): Readonly<LogresPlayableFieldTilePoint> {
  const raw =
    projectLogresPlayableFieldTile(
      tile,
    )

  return Object.freeze({
    x:
      transform.width /
        2 +
      (
        raw.x -
        transform.centerX
      ) *
        transform.fit,

    y:
      transform.height /
        2 -
      (
        raw.y -
        transform.centerY
      ) *
        transform.fit,
  })
}

export function nearestLogresPlayableFieldTile(
  x: number,
  y: number,
  tiles:
    readonly Readonly<
      LogresFieldNavigationTile
    >[],
  transform:
    LogresPlayableFieldRasterTransform,
): Readonly<LogresFieldNavigationTile> | null {
  if (
    !Number.isFinite(
      x,
    ) ||
    !Number.isFinite(
      y,
    )
  ) {
    throw new Error(
      'Field pointer coordinates must be finite',
    )
  }

  let best:
    Readonly<LogresFieldNavigationTile> | null =
      null

  let bestDistance =
    Infinity

  for (
    const tile
    of tiles
  ) {
    if (
      tile.prohibited
    ) {
      continue
    }

    const point =
      projectLogresPlayableFieldTileToRaster(
        tile,
        transform,
      )

    const dx =
      point.x -
      x

    const dy =
      point.y -
      y

    const distance =
      dx *
        dx +
      dy *
        dy

    if (
      distance <
      bestDistance
    ) {
      best =
        tile

      bestDistance =
        distance
    }
  }

  return best
}

export function chooseReconstructedLogresFieldSpawn(
  tiles:
    readonly Readonly<
      LogresFieldNavigationTile
    >[],
): Readonly<LogresFieldNavigationTile> {
  const traversable =
    tiles.filter(
      (
        tile,
      ) =>
        !tile.prohibited,
    )

  if (
    traversable.length ===
    0
  ) {
    throw new Error(
      'Playable field has no traversable tiles',
    )
  }

  let meanX =
    0

  let meanY =
    0

  for (
    const tile
    of traversable
  ) {
    const point =
      projectLogresPlayableFieldTile(
        tile,
      )

    meanX +=
      point.x

    meanY +=
      point.y
  }

  meanX /=
    traversable.length

  meanY /=
    traversable.length

  let best =
    traversable[0]!

  let bestDistance =
    Infinity

  for (
    const tile
    of traversable
  ) {
    const point =
      projectLogresPlayableFieldTile(
        tile,
      )

    const dx =
      point.x -
      meanX

    const dy =
      point.y -
      meanY

    const distance =
      dx *
        dx +
      dy *
        dy

    if (
      distance <
        bestDistance ||
      (
        distance ===
          bestDistance &&
        (
          tile.row <
            best.row ||
          (
            tile.row ===
              best.row &&
            tile.col <
              best.col
          )
        )
      )
    ) {
      best =
        tile

      bestDistance =
        distance
    }
  }

  return best
}

export async function loadLogresPlayableFieldRuntime(
  mapId:
    string =
      LOGRES_PLAYABLE_FIELD_MAP_ID,
  fetchImpl:
    typeof fetch =
      fetch,
): Promise<LoadedLogresPlayableFieldRuntime> {
  const candidate =
    await loadLogresRendererCandidate(
      mapId,
      fetchImpl,
    )

  const infoUrls =
    logresPlayableFieldInfoUrls(
      mapId,
    )

  const [
    chipBytes,
    objectBytes,
  ] =
    await Promise.all([
      fetchBinary(
        infoUrls.chip,
        fetchImpl,
      ),
      fetchBinary(
        infoUrls.object,
        fetchImpl,
      ),
    ])

  const movement =
    createLogresFieldMovementSurface(
      candidate.root,
      parseLogresMapInfoTable(
        chipBytes,
        'chip',
      ),
      parseLogresMapInfoTable(
        objectBytes,
        'object',
      ),
    )

  if (
    !movement
      .movementSurfaceComplete
  ) {
    throw new Error(
      'Recovered field movement surface is incomplete',
    )
  }

  const mesh =
    buildLogresTerrainMeshData(
      candidate.terrain,
      {
        origin:
          'top-left',
      },
    )

  return Object.freeze({
    provenance:
      LOGRES_PLAYABLE_FIELD_RUNTIME_PROVENANCE,

    mapId,

    mapBindingProvenance:
      LOGRES_PLAYABLE_FIELD_MAP_BINDING_PROVENANCE,

    projectionEvidence:
      LOGRES_PLAYABLE_FIELD_PROJECTION_EVIDENCE,

    candidate,

    movement,

    mesh,

    spawn:
      chooseReconstructedLogresFieldSpawn(
        movement.tiles,
      ),
  })
}
