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

  plugins: {
    FirebaseAuthentication: {
      skipNativeAuth:
        true,

      providers: [
        'google.com',
      ],
    },
  },
}

export default config
