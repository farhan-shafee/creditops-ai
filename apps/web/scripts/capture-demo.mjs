import { chromium, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const output = fileURLToPath(new URL('../../../docs/screenshots/', import.meta.url));
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 980 },
  reducedMotion: 'reduce',
});
const page = await context.newPage();
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
const base = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';

await page.goto(base);
await expect(page.getByText('API connected', { exact: true })).toBeVisible();
await expect(page.getByRole('button', { name: 'Run Incident Demo', exact: true })).toBeEnabled();
await expect(page.locator('.telemetry-chart').first()).toBeVisible();
await page.screenshot({ path: path.join(output, 'overview.png'), fullPage: true });
await page.waitForTimeout(1200);

for (const scenario of ['kafka-pricing-lag', 'fix-connectivity', 'db-pool-exhaustion']) {
  await page.goto(`${base}/incidents`);
  await expect(page.getByLabel('Incident scenario').locator('option')).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  await page.getByLabel('Incident scenario').selectOption(scenario);
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByTestId('incident-detail')).toBeVisible();
  await page.waitForTimeout(3200);
  await page.getByRole('button', { name: 'Investigate with AI', exact: true }).click();
  await expect(page.getByTestId('assessment')).toBeVisible();
  await page.screenshot({ path: path.join(output, `incident-${scenario}.png`), fullPage: true });
  await page.getByTestId('assessment').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1100);
  await page
    .getByTestId('assessment')
    .screenshot({ path: path.join(output, `assessment-${scenario}.png`) });
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 980 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      `${scenario} populated investigation overflows at ${width}`,
    ).toBe(false);
  }
  await page.setViewportSize({ width: 1440, height: 980 });
  if (scenario === 'kafka-pricing-lag') {
    await page.getByTestId('supporting-evidence').getByRole('button').first().click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await page.screenshot({ path: path.join(output, 'evidence-drawer.png') });
    await page.waitForTimeout(1000);
    await page.getByRole('button', { name: 'Close evidence' }).click();
  }
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
}

for (const view of [
  'observability',
  'service-map',
  'evaluations',
  'architecture',
  'runbooks',
  'history',
  'about',
]) {
  await page.goto(`${base}/${view}`);
  await expect(page.getByText('API connected', { exact: true })).toBeVisible();
  if (view === 'evaluations')
    await expect(page.getByText('Generated artifact', { exact: true })).toBeVisible();
  if (view === 'runbooks' || view === 'history')
    await expect(page.locator('.library-record').first()).toBeVisible();
  await page.screenshot({ path: path.join(output, `${view}.png`), fullPage: true });
}
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(base);
await expect(page.getByText('API connected', { exact: true })).toBeVisible();
await page.screenshot({ path: path.join(output, 'mobile-overview.png'), fullPage: true });
await page.getByRole('button', { name: 'Open navigation' }).click();
await page.screenshot({ path: path.join(output, 'mobile-navigation.png') });
await page.getByRole('button', { name: 'Close navigation' }).click();
await page.setViewportSize({ width: 320, height: 780 });
await page.goto(`${base}/architecture`);
await expect(page.getByText('API connected', { exact: true })).toBeVisible();
await expect(page.getByRole('heading', { name: 'The diagnostic path', exact: true })).toBeVisible();
await page.screenshot({ path: path.join(output, 'mobile-architecture-320.png'), fullPage: true });

if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
await context.close();
await browser.close();
console.log(
  JSON.stringify({
    output,
    browserErrors: errors.length,
    screenshots: 18,
    populatedIncidentWidthsChecked: 15,
  }),
);
