import './style.css'
import Phaser from 'phaser'
import { gameConfig } from './game/config'

const container = document.querySelector('#game-container')

if (!container) {
  throw new Error('Game container was not found.')
}

new Phaser.Game(gameConfig)
