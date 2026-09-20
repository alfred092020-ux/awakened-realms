import {
  simulateProgression,
} from '../src/game/meta/ProgressionSimulator'

const report =
  simulateProgression(
    30,
    6,
    424200,
  )

const importantDays =
  new Set([
    1,
    2,
    3,
    7,
    14,
    21,
    30,
  ])

function number(
  value: number,
) {
  return value.toFixed(1)
}

console.log('')
console.log(
  'AWAKENED REALMS'
)

console.log(
  '30-DAY IDLE PROGRESSION REPORT',
)

console.log(
  '================================',
)

for (
  const day of
  report.timeline
) {
  if (
    !importantDays.has(
      day.day,
    )
  ) {
    continue
  }

  console.log('')
  console.log(
    `DAY ${day.day}`,
  )

  console.log(
    `Average wave: ${number(day.averageWave)}`,
  )

  console.log(
    `Best wave: ${day.bestWave}`,
  )

  console.log(
    `Wins: ${day.wins}/${day.runs}`,
  )

  console.log(
    `Offline Essence: ${day.offlineEssence}`,
  )

  console.log(
    `Run Essence: ${day.runEssence}`,
  )

  console.log(
    `Purchases: ${day.purchases}`,
  )

  console.log(
    `Essence left: ${day.endingEssence}`,
  )

  console.log(
    `ATK Lv.${day.upgrades['attack-training']} | HP Lv.${day.upgrades['vitality-training']} | Haste Lv.${day.upgrades['haste-training']} | Idle Lv.${day.upgrades['idle-mastery']}`,
  )
}

console.log('')
console.log(
  'FINAL ACCOUNT',
)

console.log(
  '-------------',
)

console.log(
  `Total runs: ${report.runs}`,
)

console.log(
  `Total wins: ${report.wins}`,
)

console.log(
  `Best wave: ${report.finalBestWave}`,
)

console.log(
  `Offline Essence earned: ${report.totalOfflineEssence}`,
)

console.log(
  `Run Essence earned: ${report.totalRunEssence}`,
)

console.log(
  `Permanent upgrades bought: ${report.totalPurchases}`,
)

console.log(
  `Essence remaining: ${report.finalEssence}`,
)

console.log(
  `Attack Training: ${report.finalUpgrades['attack-training']}`,
)

console.log(
  `Vitality Training: ${report.finalUpgrades['vitality-training']}`,
)

console.log(
  `Haste Training: ${report.finalUpgrades['haste-training']}`,
)

console.log(
  `Idle Mastery: ${report.finalUpgrades['idle-mastery']}`,
)
