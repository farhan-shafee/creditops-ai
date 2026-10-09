import { chromium, expect } from '@playwright/test';
import { mkdir, rename, stat } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const output = fileURLToPath(new URL('../../../docs/screenshots/', import.meta.url));
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 980 },
  recordVideo: { dir: path.join(output, 'recording'), size: { width: 1440, height: 980 } },
});
const page = await context.newPage();
const base = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';
await page.goto(base);
await expect(page.getByRole('button', { name: 'Run Incident Demo', exact: true })).toBeEnabled();
await page.waitForTimeout(1400);
await page.getByRole('button', { name: 'Run Incident Demo', exact: true }).click();
await expect(page.getByTestId('incident-detail')).toBeVisible();
await page.waitForTimeout(3800);
await page.getByRole('button', { name: 'Investigate with AI', exact: true }).click();
await expect(page.getByTestId('assessment')).toBeVisible();
await page.locator('.trace-heading').scrollIntoViewIfNeeded();
await page.waitForTimeout(1800);
await page.getByTestId('assessment').scrollIntoViewIfNeeded();
await page.waitForTimeout(1600);
await page.getByTestId('supporting-evidence').getByRole('button').first().click();
await expect(page.getByRole('dialog')).toBeVisible();
await page.waitForTimeout(1800);
await page.getByRole('button', { name: 'Close evidence' }).click();
await page.goto(`${base}/evaluations`);
await expect(page.getByText('Generated artifact', { exact: true })).toBeVisible();
await page.waitForTimeout(1800);
const video = page.video();
await context.close();
const destination = path.join(output, 'demo.webm');
await rename(await video.path(), destination);
await browser.close();
console.log(
  JSON.stringify({
    video: destination,
    bytes: (await stat(destination)).size,
    workflow: 'Kafka incident → streamed replay → evidence → generated evaluations',
  }),
);
