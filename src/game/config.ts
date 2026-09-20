import Phaser from 'phaser'
import { BootScene } from './scenes/BootScene'
import { LoadingScene } from './scenes/LoadingScene'
import { MainMenuScene } from './scenes/MainMenuScene'

export const GAME_WIDTH = 1280
export const GAME_HEIGHT = 720

export const gameConfig: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO,
  parent: 'game-container',
  width: GAME_WIDTH,
  height: GAME_HEIGHT,
  backgroundColor: '#080b16',
  scene: [BootScene, LoadingScene, MainMenuScene],
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  render: {
    antialias: true,
    pixelArt: false,
    roundPixels: true,
  },
  input: {
    activePointers: 3,
  },
}
