import {
  getMetaModifiers,
} from './MetaProgression'

import type {
  MetaState,
} from './MetaTypes'

import type {
  RunModifiers,
  RunResult,
} from '../roguelike/RunTypes'

export function getRunModifiersForMeta(
  state: MetaState,
): RunModifiers {
  const modifiers =
    getMetaModifiers(
      state,
    )

  return {
    attackMultiplier:
      modifiers
        .attackMultiplier,

    hpMultiplier:
      modifiers
        .hpMultiplier,

    attackSpeedMultiplier:
      modifiers
        .attackSpeedMultiplier,
  }
}

export function claimRunResult(
  state: MetaState,
  result: RunResult,
) {
  state.essence +=
    Math.max(
      0,
      Math.floor(
        result.essence,
      ),
    )

  state.lifetimeRuns +=
    1

  state.bestWave =
    Math.max(
      state.bestWave,
      result.waveReached,
    )

  return state
}
