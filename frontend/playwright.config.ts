import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E tests
 * See https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './e2e',

  /* Run tests in files in parallel */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,

  /**
   * CI ではブラウザを1種に絞っているので、workersを2にして時短
   * (テストが重ければ1に戻してください)
   */
  workers: process.env.CI ? 2 : undefined,

  /* Reporter to use */
  reporter: 'html',

  /* Shared settings for all the projects below */
  use: {
    /* Run headless in Docker/CI to avoid X server dependency */
    headless: true,

    /* Stable viewport for screenshots and assertions */
    viewport: { width: 1280, height: 720 },

    /* Base URL to use in actions like `await page.goto('/')`
       CI では docker compose 内で frontend サービスが動くため、環境変数が無くても service 名を使う */
    baseURL:
      process.env.PLAYWRIGHT_BASE_URL ||
      (process.env.CI ? 'http://frontend:3000' : 'http://localhost:3000'),

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',

    /* Screenshot on failure */
    screenshot: 'only-on-failure',
  },

  /* Configure projects (CI はchromiumのみで時短) */
  projects: process.env.CI
    ? [
      {
        name: 'chromium',
        use: { ...devices['Desktop Chrome'] },
      },
    ]
    : [
      {
        name: 'chromium',
        use: { ...devices['Desktop Chrome'] },
      },
      {
        name: 'firefox',
        use: { ...devices['Desktop Firefox'] },
      },
      {
        name: 'webkit',
        use: { ...devices['Desktop Safari'] },
      },
    ],

  /* Run your local dev server before starting the tests */
  webServer: process.env.CI ? undefined : {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
