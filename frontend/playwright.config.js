import { defineConfig } from '@playwright/test';
const baseURL = process.env.ASSUREX_TEST_URL || 'http://127.0.0.1:5173';

export default defineConfig({
  testDir: './tests',
  timeout: 240000,
  expect: { timeout: 15000 },
  reporter: [['list'], ['json', { outputFile: 'reports/playwright-results.json' }]],
  fullyParallel: false,
  workers: 1,
  use: {
    actionTimeout: 15000,
    navigationTimeout: 30000,
    baseURL,
    viewport: { width: 1440, height: 1100 },
    channel: 'chrome',
    headless: true,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `node node_modules/vite/bin/vite.js ${process.env.E2E_PREVIEW ? 'preview --outDir tmp/integration-dist' : ''} --host 127.0.0.1 --port ${new URL(baseURL).port || '5173'} --strictPort`,
    url: baseURL,
    reuseExistingServer: false,
  },
});
