export class SeededRandom {
  private state: number

  constructor(
    seed: number,
  ) {
    const normalized =
      seed >>> 0

    this.state =
      normalized === 0
        ? 0x6d2b79f5
        : normalized
  }

  next() {
    let value =
      this.state

    value ^=
      value << 13

    value ^=
      value >>> 17

    value ^=
      value << 5

    this.state =
      value >>> 0

    return (
      this.state /
      0x100000000
    )
  }

  integer(
    minimum: number,
    maximum: number,
  ) {
    const min =
      Math.ceil(minimum)

    const max =
      Math.floor(maximum)

    if (max < min) {
      throw new Error(
        'Invalid random integer range.',
      )
    }

    return (
      Math.floor(
        this.next() *
          (
            max -
            min +
            1
          ),
      ) +
      min
    )
  }

  pick<T>(
    values: readonly T[],
  ): T {
    if (
      values.length === 0
    ) {
      throw new Error(
        'Cannot pick from an empty list.',
      )
    }

    const index =
      this.integer(
        0,
        values.length - 1,
      )

    const value =
      values[index]

    if (value === undefined) {
      throw new Error(
        'Random selection failed.',
      )
    }

    return value
  }

  shuffle<T>(
    values: readonly T[],
  ) {
    const result =
      [...values]

    for (
      let index =
        result.length - 1;
      index > 0;
      index -= 1
    ) {
      const swapIndex =
        this.integer(
          0,
          index,
        )

      const current =
        result[index]

      const other =
        result[swapIndex]

      if (
        current === undefined ||
        other === undefined
      ) {
        continue
      }

      result[index] =
        other

      result[swapIndex] =
        current
    }

    return result
  }
}
