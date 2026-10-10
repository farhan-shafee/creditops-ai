import { test, expect } from '@playwright/test';

const examples = [
  ['kafka-pricing-lag', 'INC-DEMO-001', /pricing-service.*Kafka consumer backlog/i],
  ['fix-connectivity', 'INC-DEMO-002', /FIX connectivity.*session instability/i],
  ['db-pool-exhaustion', 'INC-DEMO-003', /database connection pool exhaustion/i],
] as const;

for (const [scenario, incident, domain] of examples) {
  test(`${incident}: keyless recording preserves evidence, attribution and refresh`, async ({ page }) => {
    const freshDiagnostics: string[] = [];
    page.on('request', (request) => {
      if (/\/api\/diagnostics\//.test(request.url())) freshDiagnostics.push(request.url());
    });
    await page.goto('/');
    const entry = page.getByTestId('recorded-entry');
    await expect(page.getByTestId('recorded-example')).toHaveCount(3);
    await page.getByTestId('recorded-example').and(page.locator(`[data-scenario="${scenario}"]`)).click();
    await entry.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
    await expect(page.getByTestId('assessment')).toBeVisible();
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    await expect(page.getByTestId('recorded-action-summary')).toContainText('4');
    await expect(page.getByTestId('recorded-model-action')).toHaveCount(2);
    await expect(page.getByTestId('recorded-business-impact')).toBeVisible();
    await expect(page.getByTestId('investigation-provenance')).toContainText('2026-10-09T15:00:00Z');
    const comparison = page.getByTestId('assessment-comparison');
    await comparison.locator(':scope > summary').click();
    await expect(page.getByTestId('project-review-notes')).toBeVisible();
    await expect(comparison).toContainText('uncalibrated');
    const citation = page.getByTestId('supporting-evidence').getByRole('button').first();
    const identifier = await citation.innerText();
    await citation.click();
    const dialog = page.getByRole('dialog', { name: 'Evidence details' });
    await expect(dialog.getByText(identifier, { exact: true })).toBeVisible();
    await expect(dialog).toContainText('2026-10-09');
    await page.getByRole('button', { name: 'Close evidence' }).click();
    await page.reload();
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    expect(freshDiagnostics).toEqual([]);
    await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
    await expect(page.getByTestId('assessment')).not.toBeVisible();
  });
}

test('keyless showcase remains isolated, denies paid mode and fits desktop/mobile', async ({ browser, page }) => {
  await page.goto('/');
  await page.getByTestId('recorded-example').and(page.locator('[data-scenario="fix-connectivity"]')).click();
  await page.getByTestId('view-recorded-investigation').click();
  await expect(page.getByTestId('failure-domain')).toHaveText(/FIX/);
  const other = await browser.newContext();
  try {
    const second = await other.newPage();
    await second.goto('/');
    await second.getByTestId('recorded-example').and(second.locator('[data-scenario="db-pool-exhaustion"]')).click();
    await second.getByTestId('view-recorded-investigation').click();
    await expect(second.getByTestId('failure-domain')).toHaveText(/database/);
    await page.reload();
    await expect(page.getByTestId('failure-domain')).toHaveText(/FIX/);
  } finally {
    await other.close();
  }
  const denial = await page.request.post('/api/investigations', {
    data: { incident_id: 'INC-DEMO-002', mode: 'LIVE_AI' },
    headers: { Authorization: 'Bearer offline-showcase-canary' },
  });
  expect(denial.status()).toBe(403);
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['/', '/incidents', '/evaluations']) {
      await page.goto(route);
      await expect(page.getByRole('main')).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), `${route} at ${width}`).toBe(false);
    }
  }
  await expect(page.getByTestId('selected-recording-row')).toHaveCount(3);
  await expect(page.getByTestId('selected-recordings')).toContainText('Selected recorded synthetic examples');
});
