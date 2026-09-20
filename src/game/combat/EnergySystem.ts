export class EnergySystem {
  private energy: number
  private readonly maximum: number
  private readonly regenerationPerSecond: number
  private readonly onChanged: () => void

  constructor(
    maximum = 100,
    regenerationPerSecond = 8,
    onChanged: () => void = () => {},
  ) {
    this.maximum = maximum
    this.energy = maximum
    this.regenerationPerSecond = regenerationPerSecond
    this.onChanged = onChanged
  }

  update(delta: number) {
    if (this.energy >= this.maximum) {
      return
    }

    const previous = Math.floor(this.energy)

    this.energy = Math.min(
      this.maximum,
      this.energy +
        this.regenerationPerSecond *
          (delta / 1000),
    )

    if (Math.floor(this.energy) !== previous) {
      this.onChanged()
    }
  }

  canSpend(amount: number) {
    return this.energy >= amount
  }

  spend(amount: number) {
    if (!this.canSpend(amount)) {
      return false
    }

    this.energy -= amount
    this.onChanged()

    return true
  }

  getEnergy() {
    return Math.floor(this.energy)
  }

  getMaximum() {
    return this.maximum
  }
}
