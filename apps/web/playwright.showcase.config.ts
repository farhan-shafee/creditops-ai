import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  testIgnore: [],
  testMatch: '**/showcase.spec.ts',
  retries: 0,
  webServer: process.env.E2E_EXTERNAL_SERVER
    ? undefined
    : {
        command: 'pnpm --dir ../.. showcase',
        url: 'http://127.0.0.1:3000',
        reuseExistingServer: false,
        timeout: 120_000,
        gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
      },
});
