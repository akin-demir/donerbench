import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  use: {
    baseURL: 'http://127.0.0.1:5173',
    channel: 'chrome',
    screenshot: 'only-on-failure'
  },
  projects: [
    {
      name: 'desktop',
      use: { viewport: { width: 1440, height: 980 } }
    },
    {
      name: 'mobile',
      use: { ...devices['Pixel 7'] }
    }
  ]
});
