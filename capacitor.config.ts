import type {
  CapacitorConfig,
} from '@capacitor/cli'

const config:
  CapacitorConfig = {
  appId:
    'com.nexuscore.awakenedrealms',

  appName:
    'Awakened Realms',

  webDir:
    'dist',

  android: {
    allowMixedContent:
      false,
  },
}

export default config
