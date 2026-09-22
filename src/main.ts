import './style.css'
import Phaser from 'phaser'
import { gameConfig } from './game/config'

const container = document.querySelector('#game-container')

if (!container) {
  throw new Error('Game container was not found.')
}

if (new URLSearchParams(window.location.search).get('rendererProof') === '1') {
  const { showLogresRendererProof } = await import('./game/logres/field/LogresRendererProofView')
  await showLogresRendererProof(container as HTMLElement)
} else {
  const game = new Phaser.Game(gameConfig)
  Object.assign(window, { __AWAKENED_REALMS_GAME__: game })
}
