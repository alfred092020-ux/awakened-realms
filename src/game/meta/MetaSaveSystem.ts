import {
  createDefaultMetaState,
} from './MetaProgression'

import type {
  MetaState,
  MetaUpgradeLevels,
} from './MetaTypes'

const META_SAVE_KEY =
  'awakened-realms.meta.v1'

const META_UPDATED_KEY =
  'awakened-realms.meta.updated.v1'

function isObject(
  value: unknown,
): value is Record<
  string,
  unknown
> {
  return (
    typeof value ===
      'object' &&
    value !== null
  )
}

function numberOr(
  value: unknown,
  fallback: number,
) {
  return (
    typeof value ===
      'number' &&
    Number.isFinite(value)
  )
    ? value
    : fallback
}

function levelOrZero(
  value: unknown,
) {
  return Math.max(
    0,
    Math.floor(
      numberOr(
        value,
        0,
      ),
    ),
  )
}

function parseUpgradeLevels(
  value: unknown,
): MetaUpgradeLevels {
  const source =
    isObject(value)
      ? value
      : {}

  return {
    'attack-training':
      levelOrZero(
        source[
          'attack-training'
        ],
      ),

    'vitality-training':
      levelOrZero(
        source[
          'vitality-training'
        ],
      ),

    'haste-training':
      levelOrZero(
        source[
          'haste-training'
        ],
      ),

    'idle-mastery':
      levelOrZero(
        source[
          'idle-mastery'
        ],
      ),
  }
}

export class MetaSaveSystem {
  load(
    now = Date.now(),
  ): MetaState {
    const fallback =
      createDefaultMetaState(
        now,
      )

    const raw =
      localStorage.getItem(
        META_SAVE_KEY,
      )

    if (!raw) {
      return fallback
    }

    try {
      const parsed:
        unknown =
        JSON.parse(raw)

      if (
        !isObject(parsed)
      ) {
        return fallback
      }

      return {
        version:
          1,

        essence:
          Math.max(
            0,
            Math.floor(
              numberOr(
                parsed.essence,
                0,
              ),
            ),
          ),

        upgrades:
          parseUpgradeLevels(
            parsed.upgrades,
          ),

        lifetimeRuns:
          Math.max(
            0,
            Math.floor(
              numberOr(
                parsed.lifetimeRuns,
                0,
              ),
            ),
          ),

        bestWave:
          Math.max(
            0,
            Math.floor(
              numberOr(
                parsed.bestWave,
                0,
              ),
            ),
          ),

        lastSeenAt:
          Math.max(
            0,
            numberOr(
              parsed.lastSeenAt,
              now,
            ),
          ),
      }
    } catch {
      return fallback
    }
  }

  save(
    state: MetaState,
    updatedAt = Date.now(),
  ) {
    localStorage.setItem(
      META_SAVE_KEY,
      JSON.stringify(
        state,
      ),
    )

    localStorage.setItem(
      META_UPDATED_KEY,
      String(
        updatedAt,
      ),
    )
  }

  getUpdatedAt() {
    const raw =
      localStorage.getItem(
        META_UPDATED_KEY,
      )

    if (!raw) {
      return 0
    }

    const value =
      Number(raw)

    return Number.isFinite(
      value,
    )
      ? Math.max(
          0,
          value,
        )
      : 0
  }

  clear() {
    localStorage.removeItem(
      META_SAVE_KEY,
    )

    localStorage.removeItem(
      META_UPDATED_KEY,
    )
  }
}
