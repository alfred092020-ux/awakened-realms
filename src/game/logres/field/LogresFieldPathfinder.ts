import type {
  LogresFieldCoord,
  LogresFieldNavigationLookup,
  LogresFieldNavigationTile,
} from './LogresFieldNavigation'

import {
  logresFieldLinkCost,
  logresFieldLinkedNeighbors,
} from './LogresFieldNavigation'

export interface ReconstructedLogresFieldPath {
  provenance:
    'RECONSTRUCTED'

  coords:
    readonly Readonly<LogresFieldCoord>[]

  totalCost:
    number

  visitedCount:
    number
}

export interface LogresFieldPathfinderOptions {
  /**
   * RECONSTRUCTED safety bound.
   *
   * This is not an original client constant. It prevents an accidentally
   * unbounded lookup implementation from causing an infinite search.
   */
  maxVisited:
    number
}

const DEFAULT_MAX_VISITED =
  250_000

function coordKey(
  coord:
    LogresFieldCoord,
): string {
  return (
    `${coord.col},${coord.row}`
  )
}

function sameCoord(
  left:
    LogresFieldCoord,
  right:
    LogresFieldCoord,
): boolean {
  return (
    left.col ===
      right.col &&
    left.row ===
      right.row
  )
}

function requireSearchTile(
  coord:
    LogresFieldCoord,
  tileAt:
    LogresFieldNavigationLookup,
):
  | LogresFieldNavigationTile
  | undefined {
  if (
    !Number.isSafeInteger(
      coord.col,
    ) ||
    !Number.isSafeInteger(
      coord.row,
    )
  ) {
    throw new Error(
      'Logres field path coordinates must be safe integers',
    )
  }

  return tileAt(
    coord.col,
    coord.row,
  )
}

function requireMaxVisited(
  value:
    number,
): number {
  if (
    !Number.isSafeInteger(
      value,
    ) ||
    value < 1
  ) {
    throw new Error(
      'Logres field path maxVisited must be a positive safe integer',
    )
  }

  return value
}

interface QueueEntry {
  tile:
    LogresFieldNavigationTile
  cost:
    number
}

class MinQueue {
  private readonly entries:
    QueueEntry[] = []

  get size():
    number {
    return this.entries.length
  }

  push(
    entry:
      QueueEntry,
  ) {
    this.entries.push(
      entry,
    )

    let index =
      this.entries.length -
      1

    while (
      index >
      0
    ) {
      const parent =
        Math.floor(
          (
            index -
            1
          ) /
          2,
        )

      if (
        this.entries[
          parent
        ]!.cost <=
        entry.cost
      ) {
        break
      }

      this.entries[
        index
      ] =
        this.entries[
          parent
        ]!

      index =
        parent
    }

    this.entries[
      index
    ] =
      entry
  }

  pop():
    | QueueEntry
    | undefined {
    const first =
      this.entries[0]

    const last =
      this.entries.pop()

    if (
      !first ||
      !last
    ) {
      return first
    }

    if (
      this.entries
        .length ===
      0
    ) {
      return first
    }

    let index = 0

    while (true) {
      const left =
        index *
          2 +
        1
      const right =
        left +
        1

      if (
        left >=
        this.entries
          .length
      ) {
        break
      }

      let child =
        left

      if (
        right <
          this.entries
            .length &&
        this.entries[
          right
        ]!.cost <
          this.entries[
            left
          ]!.cost
      ) {
        child =
          right
      }

      if (
        this.entries[
          child
        ]!.cost >=
        last.cost
      ) {
        break
      }

      this.entries[
        index
      ] =
        this.entries[
          child
        ]!

      index =
        child
    }

    this.entries[
      index
    ] =
      last

    return first
  }
}

function reconstructPath(
  goal:
    LogresFieldNavigationTile,
  previous:
    ReadonlyMap<
      string,
      LogresFieldNavigationTile
    >,
):
  readonly Readonly<LogresFieldCoord>[] {
  const reversed:
    LogresFieldCoord[] =
    [
      {
        col:
          goal.col,
        row:
          goal.row,
      },
    ]

  let current =
    goal

  while (true) {
    const parent =
      previous.get(
        coordKey(
          current,
        ),
      )

    if (!parent) {
      break
    }

    reversed.push({
      col:
        parent.col,
      row:
        parent.row,
    })

    current =
      parent
  }

  reversed.reverse()

  return Object.freeze(
    reversed.map(
      (coord) =>
        Object.freeze(
          coord,
        ),
    ),
  )
}

/**
 * RECONSTRUCTED shortest-path implementation over CONFIRMED ORIGINAL field
 * graph rules.
 *
 * Native evidence establishes:
 * - FieldTile exposes the eight surrounding coordinates
 * - blocked/missing/excessive-level links are rejected
 * - diagonal corner cutting is rejected
 * - cardinal links cost 1
 * - diagonal links cost 2
 * - FieldTile heuristic returns 0
 *
 * With a zero heuristic, shortest-path behavior is equivalent to Dijkstra.
 * Native equal-cost adjacency/tie ordering is still UNRESOLVED, so callers must
 * not rely on one specific route when several paths have identical cost.
 */
export function findReconstructedLogresFieldPath(
  startCoord:
    LogresFieldCoord,
  goalCoord:
    LogresFieldCoord,
  tileAt:
    LogresFieldNavigationLookup,
  options:
    Partial<
      LogresFieldPathfinderOptions
    > = {},
):
  | Readonly<
      ReconstructedLogresFieldPath
    >
  | null {
  const maxVisited =
    requireMaxVisited(
      options.maxVisited ??
        DEFAULT_MAX_VISITED,
    )

  const start =
    requireSearchTile(
      startCoord,
      tileAt,
    )

  const goal =
    requireSearchTile(
      goalCoord,
      tileAt,
    )

  if (
    !start ||
    !goal ||
    start.prohibited ||
    goal.prohibited
  ) {
    return null
  }

  if (
    sameCoord(
      start,
      goal,
    )
  ) {
    return Object.freeze({
      provenance:
        'RECONSTRUCTED',
      coords:
        Object.freeze([
          Object.freeze({
            col:
              start.col,
            row:
              start.row,
          }),
        ]),
      totalCost:
        0,
      visitedCount:
        1,
    })
  }

  const queue =
    new MinQueue()

  const costs =
    new Map<
      string,
      number
    >()

  const previous =
    new Map<
      string,
      LogresFieldNavigationTile
    >()

  costs.set(
    coordKey(
      start,
    ),
    0,
  )

  queue.push({
    tile:
      start,
    cost:
      0,
  })

  let visitedCount =
    0

  while (
    queue.size >
    0
  ) {
    const current =
      queue.pop()

    if (!current) {
      break
    }

    const currentKey =
      coordKey(
        current.tile,
      )

    const bestKnown =
      costs.get(
        currentKey,
      )

    if (
      bestKnown ===
        undefined ||
      current.cost !==
        bestKnown
    ) {
      continue
    }

    visitedCount +=
      1

    if (
      visitedCount >
      maxVisited
    ) {
      return null
    }

    if (
      sameCoord(
        current.tile,
        goal,
      )
    ) {
      return Object.freeze({
        provenance:
          'RECONSTRUCTED',
        coords:
          reconstructPath(
            current.tile,
            previous,
          ),
        totalCost:
          current.cost,
        visitedCount,
      })
    }

    for (
      const neighbor
      of logresFieldLinkedNeighbors(
        current.tile,
        tileAt,
      )
    ) {
      const nextCost =
        current.cost +
        logresFieldLinkCost(
          current.tile,
          neighbor,
        )

      const neighborKey =
        coordKey(
          neighbor,
        )

      const known =
        costs.get(
          neighborKey,
        )

      if (
        known !==
          undefined &&
        known <=
          nextCost
      ) {
        continue
      }

      costs.set(
        neighborKey,
        nextCost,
      )

      previous.set(
        neighborKey,
        current.tile,
      )

      queue.push({
        tile:
          neighbor,
        cost:
          nextCost,
      })
    }
  }

  return null
}
