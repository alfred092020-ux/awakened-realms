import {
  defineConfig,
} from '@playwright/test'

export default defineConfig({
  testDir:
    './e2e',

  timeout:
    60000,

  fullyParallel:
    false,

  workers:
    1,

  use: {
    baseURL:
      'http://127.0.0.1:4174',

    headless:
      true,

    viewport: {
      width:
        720,

      height:
        1280,
    },
  },

  webServer: {
    command:
      'npm run preview -- --host 127.0.0.1 --port 4174',

    url:
      'http://127.0.0.1:4174',

    reuseExistingServer:
      false,

    timeout:
      120000,
  },
})
