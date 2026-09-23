import './style.css'
import Phaser from 'phaser'
import { gameConfig } from './game/config'

const container = document.querySelector('#game-container')

if (!container) {
  throw new Error('Game container was not found.')
}

const params =
  new URLSearchParams(
    window.location.search,
  )

const rendererCandidate =
  params.get(
    'rendererCandidate',
  )

if (
  rendererCandidate !==
  null
) {
  const {
    showLogresRendererCandidate,
  } =
    await import(
      './game/logres/field/LogresRendererCandidateView'
    )

  await showLogresRendererCandidate(
    container as HTMLElement,
    rendererCandidate,
  )
} else if (
  params.get(
    'rendererProof',
  ) ===
  '1'
) {
  const {
    showLogresRendererProof,
  } =
    await import(
      './game/logres/field/LogresRendererProofView'
    )

  await showLogresRendererProof(
    container as HTMLElement,
  )
} else {
  const game =
    new Phaser.Game(
      gameConfig,
    )

  Object.assign(
    window,
    {
      __AWAKENED_REALMS_GAME__:
        game,
    },
  )
}
