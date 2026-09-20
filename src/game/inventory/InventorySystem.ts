import {
  getItemDefinition,
} from './ItemCatalog'

import type {
  InventoryStack,
} from './ItemTypes'

export class InventorySystem {
  private readonly stacks:
    InventoryStack[] = []

  private readonly capacity: number

  constructor(
    savedStacks: InventoryStack[] = [],
    capacity = 30,
  ) {
    this.capacity = capacity

    for (const stack of savedStacks) {
      this.addItem(
        stack.itemId,
        stack.quantity,
      )
    }
  }

  addItem(
    itemId: string,
    quantity = 1,
  ) {
    const definition =
      getItemDefinition(itemId)

    if (
      !definition ||
      quantity <= 0
    ) {
      return 0
    }

    let remaining =
      Math.floor(quantity)

    const requested = remaining

    for (const stack of this.stacks) {
      if (
        stack.itemId !== itemId ||
        stack.quantity >=
          definition.maxStack
      ) {
        continue
      }

      const available =
        definition.maxStack -
        stack.quantity

      const amount =
        Math.min(
          available,
          remaining,
        )

      stack.quantity += amount
      remaining -= amount

      if (remaining <= 0) {
        break
      }
    }

    while (
      remaining > 0 &&
      this.stacks.length <
        this.capacity
    ) {
      const amount =
        Math.min(
          definition.maxStack,
          remaining,
        )

      this.stacks.push({
        itemId,
        quantity: amount,
      })

      remaining -= amount
    }

    return requested - remaining
  }

  removeItem(
    itemId: string,
    quantity = 1,
  ) {
    if (quantity <= 0) {
      return 0
    }

    let remaining =
      Math.floor(quantity)

    const requested = remaining

    for (
      let index =
        this.stacks.length - 1;
      index >= 0;
      index -= 1
    ) {
      const stack =
        this.stacks[index]

      if (
        !stack ||
        stack.itemId !== itemId
      ) {
        continue
      }

      const amount =
        Math.min(
          stack.quantity,
          remaining,
        )

      stack.quantity -= amount
      remaining -= amount

      if (stack.quantity <= 0) {
        this.stacks.splice(
          index,
          1,
        )
      }

      if (remaining <= 0) {
        break
      }
    }

    return requested - remaining
  }

  countItem(itemId: string) {
    let total = 0

    for (const stack of this.stacks) {
      if (stack.itemId === itemId) {
        total += stack.quantity
      }
    }

    return total
  }

  hasItem(
    itemId: string,
    quantity = 1,
  ) {
    return (
      this.countItem(itemId) >=
      quantity
    )
  }

  getStacks() {
    return this.stacks.map(
      (stack) => ({
        ...stack,
      }),
    )
  }

  getUsedSlots() {
    return this.stacks.length
  }

  getCapacity() {
    return this.capacity
  }

  isFull() {
    return (
      this.stacks.length >=
      this.capacity
    )
  }
}
