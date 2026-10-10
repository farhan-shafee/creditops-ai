// Capture the existing keyless application, including a clearly labeled playback video.
import { chromium, expect as baseExpect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const output = fileURLToPath(new URL('../../../docs/screenshots/', import.meta.url));
const videoTemporary = fileURLToPath(new URL('../../../artifacts/runtime/showcase-video/', import.meta.url));
const base = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';
const expect = baseExpect.configure({ timeout: 20_000 });
await mkdir(output, { recursive: true });
await mkdir(videoTemporary, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 980 },
  reducedMotion: 'reduce',
  recordVideo: { dir: videoTemporary, size: { width: 1440, height: 980 } },
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
const screenshots = [];
async function save(name, target = page, fullPage = false) {
  await target.screenshot({ path: path.join(output, name), ...(target === page ? { fullPage } : {}) });
  screenshots.push(name);
}
async function connected() {
  await expect(page.getByText('API connected', { exact: true })).toBeVisible();
}
try {
  await page.goto(base);
  await expect(page.getByTestId('recorded-entry')).toBeVisible();
  await connected();
  await save('showcase-entry.png', page, true);
  await page.waitForTimeout(3000);
  await page.getByTestId('recorded-example').and(page.locator('[data-scenario="fix-connectivity"]')).click();
  await page.waitForTimeout(2000);
  await page.getByTestId('view-recorded-investigation').click();
  await expect(page.getByTestId('assessment')).toBeVisible();
  await expect(page.getByTestId('failure-domain')).toHaveText(/FIX connectivity/);
  await expect(page.getByTestId('recorded-business-impact')).toBeVisible();
  await page.getByTestId('recorded-business-impact').scrollIntoViewIfNeeded();
  await save('showcase-business-impact.png', page.getByTestId('recorded-business-impact'));
  await page.waitForTimeout(4000);
  const citation = page.getByTestId('recorded-business-impact').getByRole('button', { name: 'BUSINESS-002-007', exact: true });
  await citation.click();
  await expect(page.getByRole('dialog', { name: 'Evidence details' })).toBeVisible();
  await save('showcase-impact-evidence.png');
  await page.waitForTimeout(5000);
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByTestId('assessment-comparison').locator(':scope > summary').click();
  await expect(page.getByTestId('project-review-notes')).toBeVisible();
  await page.getByTestId('assessment-comparison').scrollIntoViewIfNeeded();
  await save('showcase-proposal-validation.png', page.getByTestId('assessment-comparison'));
  await page.waitForTimeout(5000);
  await page.getByTestId('assessment').scrollIntoViewIfNeeded();
  await save('showcase-final-advisory.png', page.getByTestId('assessment'));
  await page.waitForTimeout(4000);
  await page.goto(`${base}/evaluations`);
  await expect(page.getByTestId('selected-recording-row')).toHaveCount(3);
  await connected();
  await save('showcase-results.png', page.getByTestId('selected-recordings'));
  await page.waitForTimeout(5000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(base);
  await expect(page.getByTestId('recorded-entry')).toBeVisible();
  await connected();
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
    throw new Error('Showcase entry overflows mobile viewport');
  }
  await save('showcase-mobile.png', page, true);
  await page.waitForTimeout(2000);
  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  console.log(JSON.stringify({ screenshots, video: 'showcase-playback.webm', label: 'Recorded investigation playback; no new model calls' }));
} finally {
  const video = page.video();
  await context.close();
  if (video) await video.saveAs(path.join(output, 'showcase-playback.webm'));
  await browser.close();
}
