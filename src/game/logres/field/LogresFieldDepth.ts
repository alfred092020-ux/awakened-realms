export const LOGRES_FIELD_DEPTH_FORMULA_EVIDENCE =
  'CONFIRMED_ORIGINAL_CURRENT_JP_NATIVE' as const

export const LOGRES_GLOBAL_FIELD_DEPTH_APPLICATION =
  'SUPPORTED_INFERENCE' as const

const DEPTH_SCALE =
  Math.fround(
    0.1,
  )

const HALF =
  Math.fround(
    0.5,
  )

const TOP_OFFSET_SCALE =
  Math.fround(
    0.05,
  )

function requireNativeDepth(
  depth: number,
): number {
  if (
    !Number.isInteger(
      depth,
    ) ||
    depth < 0 ||
    depth >
      0xffffffff
  ) {
    throw new Error(
      'Logres depth must fit native uint32',
    )
  }

  return depth
}
/**
 * Current-JP native FieldConstant::depthToZ(unsigned int).
 *
 * CONFIRMED ORIGINAL:
 *   ucvtf(depth) -> * 0.1f -> * 0.5f
 *
 * Applying this later native formula to May-2017 Global remains
 * SUPPORTED INFERENCE until target-era code is recovered.
 */
export function logresDepthToZ(
  depth: number,
): number {
  requireNativeDepth(
    depth,
  )

  const asFloat =
    Math.fround(
      depth,
    )

  const scaled =
    Math.fround(
      asFloat *
        DEPTH_SCALE,
    )

  return Math.fround(
    scaled *
      HALF,
  )
}
/**
 * Current-JP native FieldTile::depthToZOrderOfTop(unsigned int).
 *
 * Native code computes depthToZ(depth), computes depthToZ(1), then performs
 * one float32 FMADD with the 0.05f constant. JavaScript evaluates the
 * float32 inputs in double precision and Math.fround applies the single final
 * rounding, matching the observed single-precision result for this expression.
 */
export function logresDepthToTopZ(
  depth: number,
): number {
  const base =
    logresDepthToZ(
      depth,
    )

  const one =
    logresDepthToZ(
      1,
    )

  return Math.fround(
    base +
      one *
        TOP_OFFSET_SCALE,
  )
}
