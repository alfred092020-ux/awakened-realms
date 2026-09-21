import Phaser from 'phaser'

import {
  BootScene,
} from './scenes/BootScene'

import {
  LoadingScene,
} from './scenes/LoadingScene'

import {
  LogresTitleScene,
} from './scenes/LogresTitleScene'

import {
  LogresCharacterCreateScene,
} from './scenes/LogresCharacterCreateScene'

import {
  LogresFieldScene,
} from './scenes/LogresFieldScene'

export const GAME_WIDTH =
  720

export const GAME_HEIGHT =
  1280

export const gameConfig:
  Phaser.Types.Core.GameConfig = {
  type:
    Phaser.AUTO,

  parent:
    'game-container',

  width:
    GAME_WIDTH,

  height:
    GAME_HEIGHT,

  physics: {
    default:
      'arcade',

    arcade: {
      gravity: {
        x: 0,
        y: 0,
      },

      debug:
        false,
    },
  },

  scene: [
    BootScene,
    LoadingScene,
    LogresTitleScene,
    LogresCharacterCreateScene,
    LogresFieldScene,
  ],

  scale: {
    mode:
      Phaser.Scale.FIT,

    autoCenter:
      Phaser.Scale.CENTER_BOTH,
  },

  render: {
    antialias:
      true,

    pixelArt:
      false,

    roundPixels:
      true,
  },

  input: {
    activePointers:
      3,
  },
}
