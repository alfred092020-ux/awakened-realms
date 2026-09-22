/*
 * Strict Logres reconstruction preserves
 * recovered client timing values.
 *
 * Keep this helper so evidence-backed scene
 * code can state original milliseconds
 * directly without hidden acceleration.
 */
export const LOGRES_DEV_SPEED = 1

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
