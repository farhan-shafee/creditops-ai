import { chromium, expect as baseExpect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const output = fileURLToPath(new URL('../../../docs/screenshots/', import.meta.url));
const expect = baseExpect.configure({ timeout: 20_000 });
await mkdir(output, { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 980 },
  reducedMotion: 'reduce',
});
const page = await context.newPage();
const base = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:3000';
const errors = [];
page.on('pageerror', (error) => errors.push(error.message));
const screenshots = [];
const save = async (locator, name, options = {}) => {
  await locator.screenshot({ path: path.join(output, name), ...options });
  screenshots.push(name);
};

try {
  for (const scenario of ['kafka-pricing-lag', 'fix-connectivity', 'db-pool-exhaustion']) {
    await page.goto(`${base}/incidents`);
    await expect(page.getByLabel('Incident scenario').locator('option')).toHaveCount(3);
    await page.getByLabel('Incident scenario').selectOption(scenario);
    await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
    const business = page.getByTestId('business-impact');
    await expect(business).toBeVisible();
    if (scenario === 'kafka-pricing-lag') {
      await expect(business.getByTestId('impact-expired-deadlines')).toHaveText('2 / 1');
    } else if (scenario === 'fix-connectivity') {
      await expect(business.getByTestId('impact-acknowledgements')).toHaveText('0 / 2');
    } else {
      await expect(business.getByTestId('impact-processing-timeouts')).toHaveText('2');
    }
    await save(page.locator('.business-impact-panel'), `second-pass-impact-${scenario}.png`);
    if (scenario === 'kafka-pricing-lag') {
      await page.getByLabel('Investigation path').selectOption('MCP_DEMO');
      await page
        .getByRole('button', { name: 'Run adaptive MCP investigation', exact: true })
        .click();
      await expect(page.getByTestId('assessment')).toBeVisible();
      await expect(page.getByTestId('investigation-provenance')).toContainText(
        'Transport: MCP stdio',
      );
      await save(page.locator('.investigator'), 'second-pass-adaptive-mcp.png');
      const citation = business
        .getByTestId('request-journey')
        .first()
        .getByRole('button', { name: /^BUSINESS-/ })
        .first();
      await citation.click();
      await expect(page.getByRole('dialog')).toContainText('RFQ-DEMO-001-001');
      await save(page, 'second-pass-business-evidence.png');
      await page.getByRole('button', { name: 'Close evidence' }).click();
    }
    if (scenario === 'db-pool-exhaustion') {
      await page.getByLabel('Investigation path').selectOption('REPLAY');
      await page.getByRole('button', { name: 'Investigate with AI', exact: true }).click();
      await expect(page.getByTestId('assessment')).toBeVisible();
      await expect(page.getByTestId('failure-domain')).toHaveText(
        'database connection pool exhaustion',
      );
      await save(page.getByTestId('assessment'), 'second-pass-db-assessment.png');
    }
    if (scenario === 'fix-connectivity') {
      await page.setViewportSize({ width: 320, height: 800 });
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(
        false,
      );
      await save(page.locator('.business-impact-panel'), 'second-pass-mobile-320.png');
      await page.setViewportSize({ width: 1440, height: 980 });
    }
    await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  }
  await page.goto(`${base}/evaluations`);
  await expect(page.getByText('Generated artifact', { exact: true })).toBeVisible();
  await expect(
    page.getByText('Invalid references (legacy metric)', { exact: true }).first(),
  ).toBeVisible();
  await save(page, 'second-pass-evaluations.png', { fullPage: true });
  if (errors.length) throw new Error(`Browser errors: ${errors.join('; ')}`);
  console.log(JSON.stringify({ output, screenshots, browserErrors: errors.length }));
} finally {
  await context.close();
  await browser.close();
}
