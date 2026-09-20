import {
  simulateManyRuns,
} from '../src/game/roguelike/MassSimulation'

const reports =
  simulateManyRuns(
    1000,
    1000,
  )

function percent(
  value: number,
) {
  return (
    value *
    100
  ).toFixed(1) + '%'
}

function number(
  value: number,
) {
  return value
    .toFixed(1)
}

console.log('')
console.log(
  'AWAKENED REALMS'
)

console.log(
  'IDLE ROGUELIKE BALANCE REPORT',
)

console.log(
  '==============================',
)

for (
  const report of reports
) {
  console.log('')
  console.log(
    `[${report.name}]`,
  )

  console.log(
    `Runs: ${report.runs}`,
  )

  console.log(
    `Win rate: ${percent(report.winRate)}`,
  )

  console.log(
    `Average wave: ${number(report.averageWave)}`,
  )

  console.log(
    `Wave range: ${report.minimumWave} - ${report.maximumWave}`,
  )

  console.log(
    `Boss 10: ${percent(report.boss10ReachRate)}`,
  )

  console.log(
    `Boss 20: ${percent(report.boss20ReachRate)}`,
  )

  console.log(
    `Boss 30: ${percent(report.boss30ReachRate)}`,
  )

  console.log(
    `Average kills: ${number(report.averageKills)}`,
  )

  console.log(
    `Average gold: ${number(report.averageGold)}`,
  )

  console.log(
    `Average essence: ${number(report.averageEssence)}`,
  )

  console.log(
    `Average time: ${number(report.averageDurationSeconds)} sec`,
  )

  console.log(
    'Upgrade picks:',
  )

  for (
    const [
      upgrade,
      count,
    ] of Object.entries(
      report.upgradePicks,
    )
  ) {
    console.log(
      `  ${upgrade}: ${count}`,
    )
  }
}
