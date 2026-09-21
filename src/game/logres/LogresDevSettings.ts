/*
 * DEVELOPMENT-ONLY speed override.
 *
 * Original Logres timing values remain in the
 * reconstructed scenes as the source values.
 *
 * 5 means animations/delays run 5x faster.
 */
export const LOGRES_DEV_SPEED = 5

export function logresDevMs(
  originalMs: number,
) {
  return Math.max(
    1,
    Math.round(
      originalMs /
      LOGRES_DEV_SPEED,
    ),
  )
}
