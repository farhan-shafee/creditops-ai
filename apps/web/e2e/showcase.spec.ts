import { withRefreshProbe, recordedPresentation } from './console-refresh-probe';
import { withResetRouteOwner } from './reset-route-owner';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { resolve } from 'node:path';
import type { Investigation } from '../src/lib/types';
function loadAcceptanceRecording(id: string): Investigation {
  return JSON.parse(
    readFileSync(resolve(process.cwd(), '../../data/showcase', id + '.json'), 'utf8'),
  ).payload.investigation;
}
import { test, expect } from './acceptance';

async function expectHandoffPrintCanvas(page: import('@playwright/test').Page) {
  const canvas = await page.evaluate(() => ({
    colorScheme: getComputedStyle(document.documentElement).colorScheme,
    rootBackground: getComputedStyle(document.documentElement).backgroundColor,
    bodyBackground: getComputedStyle(document.body).backgroundColor,
  }));
  expect(canvas).toEqual({
    colorScheme: 'light',
    rootBackground: 'rgb(255, 255, 255)',
    bodyBackground: 'rgb(255, 255, 255)',
  });
}

const examples = [
  ['kafka-pricing-lag', 'INC-DEMO-001', /pricing-service.*Kafka consumer backlog/i],
  ['fix-connectivity', 'INC-DEMO-002', /FIX connectivity.*session instability/i],
  ['db-pool-exhaustion', 'INC-DEMO-003', /database connection pool exhaustion/i],
] as const;

for (const [scenario, incident, domain] of examples) {
  test(`${incident}: keyless recording preserves evidence, attribution and refresh`, async ({
    page,
  }) => {
    const freshDiagnostics: string[] = [];
    page.on('request', (request) => {
      if (/\/api\/diagnostics\//.test(request.url())) freshDiagnostics.push(request.url());
    });
    await page.goto('/');
    const entry = page.getByTestId('recorded-entry');
    await expect(page.getByTestId('recorded-example')).toHaveCount(3);
    await page
      .getByTestId('recorded-example')
      .and(page.locator(`[data-scenario="${scenario}"]`))
      .click();
    await entry.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
    await expect(page.getByTestId('assessment')).toBeVisible();
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    await expect(page.getByTestId('recorded-action-summary')).toContainText('4');
    await expect(page.getByTestId('recorded-model-action')).toHaveCount(2);
    await expect(page.getByTestId('recorded-business-impact')).toBeVisible();
    await expect(page.getByTestId('investigation-provenance')).toContainText(
      '2026-10-09T15:00:00Z',
    );
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

test('keyless showcase remains isolated, denies paid mode and fits desktop/mobile', async ({
  browser,
  page,
}) => {
  await page.goto('/');
  await page
    .getByTestId('recorded-example')
    .and(page.locator('[data-scenario="fix-connectivity"]'))
    .click();
  await page.getByTestId('view-recorded-investigation').click();
  await expect(page.getByTestId('failure-domain')).toHaveText(/FIX/);
  const other = await browser.newContext();
  try {
    const second = await other.newPage();
    await second.goto('/');
    await second
      .getByTestId('recorded-example')
      .and(second.locator('[data-scenario="db-pool-exhaustion"]'))
      .click();
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
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
        `${route} at ${width}`,
      ).toBe(false);
    }
  }
  await expect(page.getByTestId('selected-recording-row')).toHaveCount(3);
  await expect(page.getByTestId('selected-recordings')).toContainText(
    'Selected recorded synthetic examples',
  );
});

async function openWorkspace(page: import('@playwright/test').Page) {
  await page.goto('/');
  await page
    .getByTestId('recorded-example')
    .and(page.locator('[data-scenario="kafka-pricing-lag"]'))
    .click();
  await page.getByTestId('view-recorded-investigation').click();
  await expect(page).toHaveURL(/\/incidents/);
  await expect(page.getByTestId('recorded-workspace')).toBeVisible();
  await expect(
    page.getByTestId('recorded-workspace').locator('.recorded-facts dd').nth(1),
  ).toHaveText('complete');
}
test('workspace shell: manual keyboard tabs retain focus and activation', async ({ page }) => {
  await openWorkspace(page);
  const overview = page.getByRole('tab', { name: 'Overview', exact: true }),
    evidence = page.getByRole('tab', { name: 'Evidence', exact: true });
  await overview.focus();
  await page.keyboard.press('ArrowRight');
  await expect(evidence).toBeFocused();
  await expect(overview).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('Enter');
  await expect(evidence).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: 'Handoff', exact: true })).toBeFocused();
  await page.keyboard.press('Home');
  await expect(overview).toBeFocused();
  await page.keyboard.press('Space');
  await expect(overview).toHaveAttribute('aria-selected', 'true');
});
test('workspace shell: linked timeline exact drawer, overlaps, filters and reveal', async ({
  page,
}) => {
  const diagnostics: string[] = [],
    runs: string[] = [];
  page.on('request', (request) => {
    if (/\/api\/diagnostics\//.test(request.url())) diagnostics.push(request.url());
    if (request.method() === 'POST' && /\/api\/investigations$/.test(request.url()))
      runs.push(request.url());
  });
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const table = page.getByRole('table', { name: 'Recorded observations' });
  const row = table.locator('tbody tr[data-source-id="LOG-001-001"]');
  const id = await row.getAttribute('data-source-id');
  const instant = await row.getAttribute('data-timestamp');
  const trigger = row.getByRole('button');
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Evidence details' });
  await expect(dialog.getByText(id!, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(trigger).toBeFocused();
  await expect(row).toHaveAttribute('data-selected', 'true');
  const same = table.locator('tr[data-timestamp="' + instant + '"]');
  expect(await same.count()).toBeGreaterThan(1);
  const sameMarkers = page.locator('[data-testid="timeline-marker"][data-instant-selected="true"]');
  expect(await sameMarkers.count()).toBe(await same.count());
  for (let i = 0; i < (await same.count()); i++)
    await expect(same.nth(i)).toHaveAttribute('data-instant-selected', 'true');
  const marker = page.locator('[data-testid="timeline-marker"][data-source-id="' + id + '"]');
  await marker.click();
  await expect(dialog.getByText(id!, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  const chooser = page.getByRole('button', { name: /Choose overlapping sources/ }).first();
  await chooser.click();
  const overlaps = page.getByRole('group', { name: 'Overlapping recorded sources' });
  const tied = await overlaps.getByRole('button').count();
  expect(tied).toBeGreaterThan(1);
  const ids = (await chooser.getAttribute('data-source-ids'))!.split('|');
  expect(tied).toBe(ids.length);
  for (const tiedId of ids)
    await expect(overlaps.getByRole('button', { name: tiedId, exact: true })).toBeVisible();
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  await expect(page.getByTestId('selected-source-state')).toContainText('Hidden by filters');
  await page
    .getByTestId('selected-source-state')
    .getByRole('button', { name: 'Open selected source' })
    .click();
  await expect(dialog).toContainText('Hidden by filters');
  await dialog.getByRole('button', { name: 'Reveal source' }).click();
  await expect(dialog).not.toContainText('Hidden by filters');
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(table.locator('tr[data-source-id="' + id + '"]')).toHaveAttribute(
    'data-selected',
    'true',
  );
  expect(errors).toEqual([]);
  expect(diagnostics).toEqual([]);
  expect(runs).toHaveLength(1);
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .first()
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await expect(page.getByRole('tab', { name: 'Overview', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(page.getByTestId('selected-source-state')).toHaveCount(0);
  await expect(page.getByLabel('Service filter')).toHaveValue('');
  await expect(page.getByRole('dialog', { name: 'Evidence details' })).toHaveCount(0);
});
test('workspace shell: missing context never requests current evidence; responsive ranges', async ({
  page,
}) => {
  const lookups: string[] = [];
  page.on('request', (r) => {
    if (/\/api\/evidence\//.test(r.url())) lookups.push(r.url());
  });
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const context = page.getByTestId('missing-recorded-context');
  await expect(context).toContainText('not returned');
  expect(await context.getByRole('button').count()).toBe(0);
  await page.getByLabel('UTC start').fill('not-a-time');
  await expect(page.getByRole('alert').filter({ hasText: 'valid UTC' })).toBeVisible();
  await page.getByRole('button', { name: 'Reset display filters' }).click();
  await page.getByLabel('UTC start').fill('2026-10-09T00:00:00Z');
  await expect(
    page.getByRole('alert').filter({ hasText: 'within returned-sample coverage' }),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Reset display filters' }).click();
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > innerWidth),
      'Document overflow at ' + width,
    ).toBe(false);
  }
  expect(lookups).toEqual([]);
});

test('workspace shell: lexical metric default reset and off-default selection', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const metric = page.getByLabel('Metric and unit');
  const first = (await metric.locator('option').nth(1).getAttribute('value'))!;
  const second = (await metric.locator('option').nth(2).getAttribute('value'))!;
  await expect(metric).toHaveValue(first);
  await metric.selectOption('');
  await expect(metric).toHaveValue('');
  const offMarker = page.locator('.recorded-lane').nth(1).getByTestId('timeline-marker').first();
  const sourceId = (await offMarker.getAttribute('data-source-id'))!;
  const sourceRow = page
    .getByRole('table', { name: 'Recorded observations' })
    .locator('tr[data-source-id="' + sourceId + '"]');
  await sourceRow.getByRole('button').click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByRole('button', { name: 'Reset display filters' }).click();
  await expect(metric).toHaveValue(first);
  await expect(sourceRow).toHaveCount(0);
  await expect(page.getByTestId('selected-source-state')).toContainText(sourceId);
  await expect(page.getByTestId('selected-source-state')).toContainText('Hidden by filters');
  await page
    .getByTestId('selected-source-state')
    .getByRole('button', { name: 'Open selected source' })
    .click();
  const dialog = page.getByRole('dialog', { name: 'Evidence details' });
  await expect(dialog).toContainText('Hidden by filters');
  await dialog.getByRole('button', { name: 'Reveal source' }).click();
  await expect(dialog).not.toContainText('Hidden by filters');
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(metric).toHaveValue(second);
  await expect(sourceRow).toHaveAttribute('data-selected', 'true');
});
test('workspace shell: keyboard Reveal retains modal focus and trap', async ({ page }) => {
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .getByRole('table', { name: 'Recorded observations' })
    .locator('tr[data-source-id="LOG-001-001"]')
    .getByRole('button')
    .click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  const trigger = page
    .getByTestId('selected-source-state')
    .getByRole('button', { name: 'Open selected source' });
  await trigger.click();
  const close = page.getByRole('button', { name: 'Close evidence' });
  const dialog = page.getByRole('dialog', { name: 'Evidence details' });
  await expect(close).toBeFocused();
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeEnabled();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(dialog).not.toContainText('Hidden by filters');
  await expect(close).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Pin source', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Pin source', exact: true })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Escape');
  // Evidence Reveal returns to the exact source; ordinary close still returns to its trigger.
  await expect(
    page
      .getByRole('table', { name: 'Recorded observations' })
      .locator('tr[data-source-id="LOG-001-001"]')
      .getByRole('button', { name: 'LOG-001-001', exact: true }),
  ).toBeFocused();
});
test('workspace shell: Overview citation Reveal close restores a visible trigger', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  const overview = page.getByRole('tab', { name: 'Overview', exact: true });
  await overview.click();
  const citation = page.getByTestId('supporting-evidence').getByRole('button').first();
  const sourceId = await citation.innerText();
  await citation.click();
  const dialog = page.getByRole('dialog', { name: 'Evidence details' });
  await expect(dialog.getByText(sourceId, { exact: true })).toBeVisible();
  await expect(dialog).toContainText('Hidden by filters');
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeEnabled();
  await page.keyboard.press('Tab');
  await expect(dialog.getByRole('button', { name: 'Reveal source' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(dialog).not.toContainText('Hidden by filters');
  await expect(overview).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('Escape');
  await expect(citation).toBeVisible();
  await expect(citation).toBeFocused();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(page.getByTestId('selected-source-state')).toContainText(sourceId);
  await expect(page.getByTestId('selected-source-state')).not.toContainText('Hidden by filters');
});
test('workspace notes: refresh restores personal state and resets display without investigation POST', async ({
  page,
}) => {
  await openWorkspace(page);
  const posts: string[] = [];
  page.on('request', (r) => {
    if (r.method() === 'POST' && /\/api\/investigations/.test(r.url())) posts.push(r.url());
  });
  const note = page.getByLabel('Personal note');
  await note.fill('<img src=x onerror=alert(1)>');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Service filter').selectOption('pricing-service');
  await page.reload();
  await expect(note).toHaveValue('<img src=x onerror=alert(1)>');
  await expect(page.getByRole('tab', { name: 'Overview', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(page.getByLabel('Service filter')).toHaveValue('');
  await page.getByRole('button', { name: 'Reset display filters', exact: true }).click();
  await expect(note).toHaveValue('<img src=x onerror=alert(1)>');
  expect(posts).toEqual([]);
});
test('workspace notes: failed reset preserves notes and successful reset clears captured incident', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('captured note');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.route('**/api/demo/scenarios/kafka-pricing-lag/reset', (route) =>
    route.fulfill({ status: 500, json: { detail: 'Reset failed' } }),
  );
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByText('Reset failed', { exact: true })).toBeVisible();
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await expect(page.getByRole('button', { name: 'Unpin source', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(page.getByLabel('Personal note')).toHaveValue('captured note');
  await page.reload();
  await expect(page.getByLabel('Personal note')).toHaveValue('captured note');
  await page.unroute('**/api/demo/scenarios/kafka-pricing-lag/reset');
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByTestId('recorded-workspace')).not.toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(() =>
        Object.keys(sessionStorage).filter((k) => k.startsWith('creditops-workspace:v1:')),
      ),
    )
    .toEqual([]);
});
test('workspace acceptance: denied storage keeps edits in memory with refresh warning', async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(window, 'sessionStorage', {
      get() {
        throw Error('denied');
      },
    }),
  );
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('memory note');
  await expect(page.getByTestId('personal-workspace')).toContainText(/lost on refresh/);
  await expect(page.getByLabel('Personal note')).toHaveValue('memory note');
});
test('workspace acceptance: malformed entry has current-record clear option', async ({ page }) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('create entry');
  await page.evaluate(() => {
    const key = Object.keys(sessionStorage).find((k) => k.startsWith('creditops-workspace:v1:'))!;
    sessionStorage.setItem(key, 'malformed');
  });
  await page.reload();
  await expect(page.getByTestId('personal-workspace')).toContainText(/invalid/i);
  await page
    .getByRole('button', { name: 'Clear current record notes and pins', exact: true })
    .click();
  await expect(page.getByLabel('Personal note')).toHaveValue('');
  await expect(page.getByTestId('personal-workspace')).not.toContainText(/invalid/i);
});
test('workspace notes: record switches restore own entries and separate tabs do not synchronize', async ({
  page,
  context,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('kafka personal');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await expect(page.getByLabel('Personal note')).toHaveValue('');
  await expect(page.getByTestId('personal-workspace')).toContainText('0 / 20');
  await page.getByLabel('Personal note').fill('database personal');
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-001');
  await expect(page.getByLabel('Personal note')).toHaveValue('kafka personal');
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
  const other = await context.newPage();
  try {
    await other.goto('/incidents');
    await expect(other.getByLabel('Personal note')).toHaveValue('');
    await other.getByLabel('Personal note').fill('other tab');
    await expect(page.getByLabel('Personal note')).toHaveValue('kafka personal');
    await page.reload();
    await expect(page.getByLabel('Personal note')).toHaveValue('kafka personal');
  } finally {
    await other.close();
  }
});
test('workspace acceptance: full storage warns while locked reset clears captured scope only', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('kafka note');
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await page.getByLabel('Personal note').fill('database note');
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.getByLabel('Personal note')).toHaveValue('kafka note');
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let reached!: () => void;
  const started = new Promise<void>((resolve) => {
    reached = resolve;
  });
  await page.route('**/api/demo/scenarios/kafka-pricing-lag/reset', async (route) => {
    reached();
    await gate;
    await route.continue();
  });
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await started;
  await expect(page.getByRole('dialog')).toHaveCount(0);
  // A forced event is blocked by scenarioOperationRef; it does not advance selection generation.
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion', { force: true });
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-001');
  await expect(page.getByLabel('Personal note')).toHaveValue('kafka note');
  release();
  await expect(page.getByTestId('scenario-selection-state')).toContainText('not loaded');
  await expect(page.getByLabel('Incident scenario')).toHaveValue('kafka-pricing-lag');
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await expect(page.getByLabel('Personal note')).toHaveValue('database note');
  await expect
    .poll(() =>
      page.evaluate(() =>
        Object.keys(sessionStorage)
          .filter((k) => k.startsWith('creditops-workspace:v1:'))
          .map((k) => sessionStorage.getItem(k))
          .join(''),
      ),
    )
    .not.toContain('kafka note');
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k, v) {
      if (k.startsWith('creditops-workspace:v1:')) throw Error('quota');
      original.call(this, k, v);
    };
  });
  await page.getByLabel('Personal note').fill('memory retained');
  await expect(page.getByTestId('personal-workspace')).toContainText('lost on refresh');
  await expect(page.getByLabel('Personal note')).toHaveValue('memory retained');
});
test('workspace notes: unpin from personal citation retains a visible close focus target', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Close evidence' })).toBeFocused();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page
    .getByTestId('personal-workspace')
    .getByRole('button')
    .filter({ has: page.locator('svg') })
    .first()
    .click();
  await page.getByRole('button', { name: 'Unpin source', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Close evidence' })).toBeFocused();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await expect(
    page.getByRole('button', { name: 'Clear current record notes and pins', exact: true }),
  ).toBeFocused();
});
test('workspace acceptance: successful reset discloses removal denial and retries captured personal cleanup only', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('retained after backend reset');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.evaluate(() => {
    const current = Object.keys(sessionStorage).find((k) =>
      k.startsWith('creditops-workspace:v1:'),
    )!;
    const parts = current.split(':');
    parts[3] = 'INC-DEMO-003';
    sessionStorage.setItem(
      parts.join(':'),
      JSON.stringify({ note: 'unrelated incident', pinnedIds: [] }),
    );
    const original = Storage.prototype.removeItem;
    (window as unknown as { restorePersonalRemoval: () => void }).restorePersonalRemoval = () => {
      Storage.prototype.removeItem = original;
    };
    Storage.prototype.removeItem = function (key) {
      if (key.startsWith('creditops-workspace:v1:')) throw Error('raw-storage-secret-marker');
      original.call(this, key);
    };
  });
  const resets: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && /\/api\/demo\/scenarios\/.*\/reset$/.test(request.url()))
      resets.push(request.url());
  });
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByTestId('recorded-workspace')).not.toBeVisible();
  const failure = page.getByTestId('personal-cleanup-failure');
  await expect(failure).toContainText('Scenario reset succeeded');
  await expect(failure).toContainText('INC-DEMO-001');
  await expect(failure).toContainText('captured session');
  await expect(failure).toContainText('Stored notes and pins may remain');
  await expect(failure).not.toContainText('raw-storage-secret-marker');
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          Object.keys(sessionStorage).filter((k) => k.startsWith('creditops-workspace:v1:')).length,
      ),
    )
    .toBe(2);
  await failure
    .getByRole('button', { name: 'Retry personal cleanup for INC-DEMO-001', exact: true })
    .click();
  await expect(failure).toBeVisible();
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByLabel('Personal note')).toHaveValue('retained after backend reset');
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
  await page.evaluate(() =>
    (window as unknown as { restorePersonalRemoval: () => void }).restorePersonalRemoval(),
  );
  const postsBeforeRetry = resets.length;
  await failure
    .getByRole('button', { name: 'Retry personal cleanup for INC-DEMO-001', exact: true })
    .click();
  await expect(failure).toHaveCount(0);
  await expect(page.getByLabel('Personal note')).toHaveValue('');
  await expect(page.getByTestId('personal-workspace')).toContainText('0 / 20');
  const retained = await page.evaluate(() =>
    Object.keys(sessionStorage)
      .filter((k) => k.startsWith('creditops-workspace:v1:'))
      .map((k) => sessionStorage.getItem(k)),
  );
  expect(retained).toEqual([JSON.stringify({ note: 'unrelated incident', pinnedIds: [] })]);
  expect(resets.length).toBe(postsBeforeRetry);
  expect(resets).toHaveLength(1);
});

test('workspace acceptance: prepare both drafts and copy captured Markdown locally', async ({
  page,
}) => {
  await page.clock.install({ time: new Date('2030-01-02T03:00:00Z') });
  const pending = new Set<import('@playwright/test').Request>();
  page.on('request', (request) => {
    if (/\/api\//.test(request.url())) pending.add(request);
  });
  page.on('requestfinished', (request) => pending.delete(request));
  page.on('requestfailed', (request) => pending.delete(request));
  await page.addInitScript(() => {
    (window as unknown as { printed: number }).printed = 0;
    window.print = () => {
      (window as unknown as { printed: number }).printed += 1;
    };
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async (text: string) => {
          (window as unknown as { copied: string }).copied = text;
        },
      },
    });
  });
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('PERSONAL-NOTE-EXPORT-CANARY');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  await page.getByRole('tab', { name: 'Handoff', exact: true }).click();
  // Freeze unrelated Console refresh timers; drain its already-started requests.
  // Every subsequent API request is still counted, including investigation POSTs.
  const refreshFinished = page.waitForResponse((response) =>
    /\/api\/metrics\/query/.test(response.url()),
  );
  await page.clock.pauseAt('2030-01-02T03:04:05Z');
  await refreshFinished;
  await expect
    .poll(async () => {
      // A browser round trip lets chained fetch continuations run before counting.
      await page.evaluate(() => undefined);
      return pending.size;
    })
    .toBe(0);
  const requests: string[] = [];
  page.on('request', (r) => {
    if (/\/api\//.test(r.url())) requests.push(r.url());
  });
  let previousMarkdown: string | null = null;
  for (const template of ['technical', 'stakeholder']) {
    await page.getByLabel('Handoff template').selectOption(template);
    await page.getByLabel('Include pinned source highlights').check();
    if (previousMarkdown !== null)
      await expect(page.getByLabel('Prepared Markdown')).toHaveValue(previousMarkdown);
    await page.getByRole('button', { name: /^(Prepare|Reprepare) draft$/ }).click();
    const preview = page.getByTestId('handoff-preview');
    await expect(preview).toContainText('Synthetic · Recorded · Draft · Human review required');
    await expect(preview).toContainText('LOG-001-001');
    await expect(preview).toContainText('Source appendix');
    await expect(preview).toContainText('Material limitations and uncertainty');
    await expect(preview).toContainText('Pinned source highlights');
    if (template === 'stakeholder') {
      const brief = preview.locator(':scope > section').first();
      await expect(brief.getByRole('heading')).toHaveText('Stakeholder brief');
      await expect(brief).toContainText('Returned events cover');
      await expect(brief).toContainText('requiring human verification');
      await expect(brief).toContainText('final business outcome');
      await expect(brief).toContainText('Please have the owning team verify');
      await expect(brief).not.toContainText('QUOTE_STALE');
      await expect(brief).not.toContainText('ACK_UNCERTAIN');
      await expect(
        preview.getByRole('heading', {
          name: 'Appendix — Material limitations and uncertainty',
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        preview.getByRole('heading', {
          name: 'Appendix — Proposed checks — human review required',
          exact: true,
        }),
      ).toBeVisible();
      await expect(
        preview.getByRole('heading', {
          name: 'Appendix — Project narrative cautions',
          exact: true,
        }),
      ).toBeVisible();
    }
    await expect(preview).not.toContainText('PERSONAL-NOTE-EXPORT-CANARY');
    const markdown = await page.getByLabel('Prepared Markdown').inputValue();
    previousMarkdown = markdown;
    const preparedAt = await preview.locator('time[data-prepared-at]').innerText();
    expect(preparedAt).toBe('2030-01-02T03:04:05.000Z');
    expect(markdown).toContain('Prepared at: ' + preparedAt);
    await page.getByRole('button', { name: 'Copy Markdown', exact: true }).click();
    await expect(page.getByRole('status').filter({ hasText: 'Markdown copied' })).toBeVisible();
    expect(await page.evaluate(() => (window as unknown as { copied: string }).copied)).toBe(
      markdown,
    );
    await page.getByRole('button', { name: 'Print draft', exact: true }).click();
    const citation = preview.getByRole('button', { name: 'LOG-001-001', exact: true }).last();
    await citation.click();
    await expect(page.getByRole('dialog', { name: 'Evidence details' })).toContainText(
      'LOG-001-001',
    );
    await page.keyboard.press('Escape');
    await expect(citation).toBeFocused();
  }
  expect(requests).toEqual([]);
  expect(await page.evaluate(() => (window as unknown as { printed: number }).printed)).toBe(2);
});
test('workspace acceptance: rejected clipboard exposes identical selectable Markdown and clean print', async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: {
        writeText: async () => {
          throw Error('denied');
        },
      },
    });
    window.print = () => {
      (window as unknown as { printed: boolean }).printed = true;
    };
  });
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('NOTE-PRINT-CANARY');
  await page.getByRole('tab', { name: 'Handoff', exact: true }).click();
  await page.getByRole('button', { name: 'Prepare draft', exact: true }).click();
  const preview = page.getByTestId('handoff-preview');
  const markdown = await page.getByLabel('Prepared Markdown').inputValue();
  await page.getByRole('button', { name: 'Copy Markdown', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Clipboard unavailable' })).toBeVisible();
  await expect(page.getByLabel('Prepared Markdown')).toBeFocused();
  expect(
    await page
      .getByLabel('Prepared Markdown')
      .evaluate((e: HTMLTextAreaElement) => e.value.slice(e.selectionStart, e.selectionEnd)),
  ).toBe(markdown);
  const printPreparedAt = await preview.locator('time[data-prepared-at]').innerText();
  expect(markdown).toContain('Prepared at: ' + printPreparedAt);
  await page.getByRole('button', { name: 'Print draft', exact: true }).click();
  expect(await page.evaluate(() => (window as unknown as { printed: boolean }).printed)).toBe(true);
  await page.emulateMedia({ media: 'print' });
  await expectHandoffPrintCanvas(page);
  await expect(preview).toBeVisible();
  await expect(preview.locator('time[data-prepared-at]')).toHaveText(printPreparedAt);
  await expect(preview).toContainText('Material limitations and uncertainty');
  await expect(preview).toContainText('Source appendix');
  await expect(
    preview.locator('.handoff-sources li[data-source-id="LOG-001-001"] .handoff-print-id'),
  ).toBeVisible();
  for (const selector of [
    '.sidebar',
    '.topbar',
    '.scenario-controls',
    '.recorded-tabs',
    '[data-testid="personal-workspace"]',
    '.handoff-controls',
    '.handoff-markdown',
    '.recorded-technical',
  ])
    await expect(page.locator(selector)).toBeHidden();
  await expect(preview.locator('button').first()).toBeHidden();
  expect(await preview.evaluate((e) => getComputedStyle(e).backgroundColor)).toBe(
    'rgb(255, 255, 255)',
  );
  for (const width of [768, 390, 320]) {
    await page.emulateMedia({ media: 'screen' });
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(
      false,
    );
  }
});

// Oracles are read-only clones of preserved packaged bytes; UI interactions remain real.
for (const [scenario, incident] of examples) {
  test(
    'workspace acceptance: ' + incident + ' full recording flow stays source-faithful and local',
    async ({ page }) => {
      const oracle = loadAcceptanceRecording(incident);
      const calls: string[] = [];
      page.on('request', (r) => {
        if (
          /\/api\/diagnostics\//.test(r.url()) ||
          (r.method() === 'POST' && /\/api\/investigations$/.test(r.url()))
        )
          calls.push(r.url());
      });
      await page.goto('/');
      await page
        .getByTestId('recorded-example')
        .and(page.locator('[data-scenario="' + scenario + '"]'))
        .click();
      await page.getByTestId('view-recorded-investigation').click();
      const workspace = page.getByTestId('recorded-workspace');
      await expect(workspace).toBeVisible();
      await expect(workspace.locator('.recorded-facts dd').nth(0)).toHaveText(
        oracle.provenance!.showcase!.recorded_execution_outcome ?? 'Not recorded',
      );
      await expect(workspace.locator('.recorded-facts dd').nth(1)).toHaveText('complete');
      await expect(page.getByTestId('failure-domain')).toHaveText(
        oracle.assessment!.probable_failure_domain,
      );
      await page.getByText('Technical provenance and diagnostic activity', { exact: true }).click();
      await expect(page.getByTestId('recorded-action-summary')).toContainText(
        '4 initial MCP checks selected by the application',
      );
      await expect(page.getByTestId('recorded-action-summary')).toContainText('1 model decision');
      await expect(page.getByTestId('recorded-action-summary')).toContainText('1 model assessment');
      await expect(page.getByTestId('recorded-action-summary')).toContainText(
        'No model-selected follow-up diagnostics',
      );
      await expect(page.getByTestId('recorded-model-action')).toHaveCount(2);
      await expect(
        page.getByText('Application-runbook initial diagnostic', { exact: true }),
      ).toHaveCount(4);
      await expect(
        page.getByText('Validator-authored assessment check', { exact: true }),
      ).toHaveCount(1);
      const business = oracle.evidence.find((e) => e.kind === 'business_event')!;
      await expect(page.getByTestId('recorded-business-impact')).toContainText(
        String(business.data.rfq_id),
      );
      if (incident === 'INC-DEMO-002') {
        await expect(page.getByTestId('recorded-business-impact')).toContainText(
          'retransmission of the same order',
        );
        const order = oracle.evidence.find((e) => e.data.retransmission === true)!;
        await expect(page.getByTestId('recorded-business-impact')).toContainText(
          String(order.data.economic_order_id ?? order.data.order_id),
        );
      }
      await page.getByLabel('Personal note').fill('personal-only-' + incident);
      await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
      const request = String(business.data.rfq_id);
      await page.getByLabel('Request filter').selectOption(request);
      const table = page.getByRole('table', { name: 'Recorded observations' });
      const businessRows = table.locator('tbody tr').filter({ hasText: '/ business_event' });
      expect(await businessRows.count()).toBe(
        oracle.evidence.filter((e) => e.kind === 'business_event' && e.data.rfq_id === request)
          .length,
      );
      const source = oracle.evidence.find((e) => e.kind === 'log')!;
      const row = table.locator('tr[data-source-id="' + source.id + '"]');
      await expect(row.locator('time')).toHaveText(source.timestamp + ' UTC');
      const trigger = row.getByRole('button');
      await trigger.click();
      const dialog = page.getByRole('dialog', { name: 'Evidence details' });
      await expect(dialog.locator('.json-source')).toHaveText(JSON.stringify(source.data, null, 2));
      await expect(dialog).toContainText(source.timestamp);
      await page.getByRole('button', { name: 'Pin source', exact: true }).click();
      await page.keyboard.press('Escape');
      await expect(trigger).toBeFocused();
      await page.getByLabel('Service filter').selectOption('fix-gateway');
      await expect(page.getByTestId('selected-source-state')).toContainText(source.id);
      await page.getByRole('button', { name: 'Reset display filters', exact: true }).click();
      await expect(page.getByLabel('Personal note')).toHaveValue('personal-only-' + incident);
      await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
      await page.getByRole('tab', { name: 'Review', exact: true }).click();
      const confidence = page
        .locator('.recorded-review-row')
        .filter({ has: page.getByRole('heading', { name: 'confidence', exact: true }) });
      await expect(confidence.getByRole('cell').nth(0)).toContainText(
        String(oracle.provider_proposal!.confidence),
      );
      await expect(confidence.getByRole('cell').nth(1)).toContainText(
        String(oracle.assessment!.confidence),
      );
      await expect(confidence).toContainText('known_domain_rule_normalization');
      await expect(confidence).toContainText('diagnostic_validation');
      await expect(
        page.getByRole('region', { name: 'Playback validation', exact: true }),
      ).toContainText('separate from recorded validation and project review notes');
      await expect(
        page.getByRole('heading', { name: 'Playback validation — separate current check' }),
      ).toBeVisible();
      await page.getByRole('tab', { name: 'Handoff', exact: true }).click();
      for (const template of ['technical', 'stakeholder']) {
        await page.getByLabel('Handoff template').selectOption(template);
        await page.getByRole('button', { name: /^(Prepare|Reprepare) draft$/ }).click();
        const markdown = await page.getByLabel('Prepared Markdown').inputValue();
        expect(markdown).toContain('Synthetic · Recorded · Draft · Human review required');
        expect(markdown).not.toContain('personal-only-' + incident);
        for (const e of oracle.evidence) {
          // Public source IDs contain literal Markdown punctuation, escaped for safe rendering.
          const literalId = e.id
            .replaceAll('-', String.fromCharCode(92) + '-')
            .replaceAll('_', String.fromCharCode(92) + '_');
          expect(markdown).toContain(literalId);
        }
        expect(
          await page
            .getByTestId('handoff-preview')
            .locator('.handoff-sources li')
            .evaluateAll((rows) => rows.map((row) => row.getAttribute('data-source-id')).sort()),
        ).toEqual(oracle.evidence.map((e) => e.id).sort());
        await expect(page.getByTestId('handoff-preview')).toContainText(
          'Material limitations and uncertainty',
        );
      }
      const countBeforeRefresh = calls.length;
      await page.reload();
      await expect(page.getByRole('tab', { name: 'Overview', exact: true })).toHaveAttribute(
        'aria-selected',
        'true',
      );
      await expect(page.getByLabel('Personal note')).toHaveValue('personal-only-' + incident);
      await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
      expect(calls.length).toBe(countBeforeRefresh);
      expect(calls).toHaveLength(1);
      await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
      await expect(workspace).toHaveCount(0);
      expect(
        await page.evaluate(() =>
          Object.keys(sessionStorage).filter((k) => k.startsWith('creditops-workspace:v1:')),
        ),
      ).toEqual([]);
    },
  );
}

test('workspace acceptance: filters show full UTC boundaries, returned lane span and observation gaps', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(
    page.getByText('Recorded assessment unchanged; filters do not rerun investigation.', {
      exact: true,
    }),
  ).toBeVisible();
  const lane = page.locator('.recorded-lane').first();
  await expect(lane.locator('.recorded-lane-boundaries')).toContainText('2026-10-09T13:59:00.000Z');
  await expect(lane.locator('.recorded-lane-boundaries')).toContainText('2026-10-09T14:02:24.000Z');
  await expect(lane.locator('.recorded-lane-coverage')).toHaveText(
    'Returned lane coverage in this display: 2026-10-09T14:01:48.000Z UTC — 2026-10-09T14:02:24.000Z UTC · 2 discrete observations.',
  );
  await expect(lane.locator('.recorded-lane-gaps')).toContainText(
    'No returned observations between',
  );
  await expect(lane).not.toContainText('15:00:00');
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  await expect(
    page.getByText('Recorded assessment unchanged; filters do not rerun investigation.', {
      exact: true,
    }),
  ).toBeVisible();
});

test('workspace acceptance: delayed restore cannot revive prior topology drawer controls or personal state', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Personal note').fill('kafka isolated note');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .getByTestId('recorded-context')
    .getByRole('button', { name: 'TOPOLOGY-001', exact: true })
    .click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await page.getByLabel('Personal note').fill('database isolated note');
  const savedKafka = await page.evaluate(() =>
    localStorage.getItem('creditops-investigation:v1:INC-DEMO-001'),
  );
  expect(savedKafka).toBeTruthy();
  let release!: () => void, reached!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const started = new Promise<void>((resolve) => {
    reached = resolve;
  });
  let completed!: () => void;
  const delivered = new Promise<void>((resolve) => {
    completed = resolve;
  });
  await page.route('**/api/investigations/' + savedKafka, async (route) => {
    const response = await route.fetch();
    reached();
    await gate;
    try {
      await route.fulfill({ response });
    } finally {
      completed();
    }
  });
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await started;
  // Restore GET leaves scenario selection enabled: this is a reachable generation change.
  await expect(page.getByLabel('Incident scenario')).toBeEnabled();
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await expect(page.getByLabel('Personal note')).toHaveValue('database isolated note');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await expect(page.getByTestId('selected-source-state')).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page
    .getByTestId('recorded-context')
    .getByRole('button', { name: 'TOPOLOGY-001', exact: true })
    .click();
  await expect(page.getByRole('button', { name: 'Pin source', exact: true })).toBeVisible();
  release();
  await delivered;
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await expect(page.getByRole('button', { name: 'Pin source', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('Personal note')).toHaveValue('database isolated note');
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
  await page.unroute('**/api/investigations/' + savedKafka);
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.getByLabel('Personal note')).toHaveValue('kafka isolated note');
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
});

test('workspace acceptance: malformed recording blocks workspace and leaves genuine selection available', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.route('**/api/investigations/*', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch();
    const body = await response.json();
    body.evidence.push(structuredClone(body.evidence[0]));
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await expect(page.getByText('Recording unavailable', { exact: true })).toBeVisible();
  await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByLabel('Incident scenario')).toBeEnabled();
  await page.unroute('**/api/investigations/*');
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-002');
});

test('workspace acceptance: every section fits 1440 768 390 320, preserves keyboard focus and reduced motion', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openWorkspace(page);
  const tabs = ['Overview', 'Evidence', 'Review', 'Handoff'];
  const overview = page.getByRole('tab', { name: 'Overview', exact: true });
  await overview.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Evidence', exact: true })).toBeFocused();
  await expect(overview).toHaveAttribute('aria-selected', 'true');
  await page.keyboard.press('Space');
  await expect(page.getByRole('tab', { name: 'Evidence', exact: true })).toHaveAttribute(
    'aria-selected',
    'true',
  );
  await page.keyboard.press('End');
  await expect(page.getByRole('tab', { name: 'Handoff', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await page.getByRole('button', { name: 'Prepare draft', exact: true }).click();
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const tab of tabs) {
      const control = page.getByRole('tab', { name: tab, exact: true });
      await control.click();
      await expect(control).toBeFocused();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        tab + ' at ' + width,
      ).toBe(true);
      const panel = page.getByRole('tabpanel', { name: tab, exact: true });
      expect(
        await panel.evaluate((e) => e.scrollWidth <= e.clientWidth),
        tab + ' panel at ' + width,
      ).toBe(true);
      const horizontalScrollers = await panel.evaluate((e) =>
        [...e.querySelectorAll<HTMLElement>('*')]
          .filter((el) => {
            const style = getComputedStyle(el);
            return (
              el.getClientRects().length > 0 &&
              /auto|scroll/.test(style.overflowX) &&
              el.scrollWidth > el.clientWidth + 1 &&
              !el.closest('.recorded-table-scroll')
            );
          })
          .map((el) => el.tagName + '.' + el.className),
      );
      expect(horizontalScrollers, tab + ' horizontal scrollers at ' + width).toEqual([]);
      if (tab === 'Evidence') {
        await page
          .getByRole('table', { name: 'Recorded observations' })
          .getByRole('button')
          .first()
          .click();
        const dialog = page.getByRole('dialog');
        expect(await dialog.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
        await page.keyboard.press('Shift+Tab');
        await expect(page.getByRole('button', { name: 'Pin source', exact: true })).toBeFocused();
        await page.keyboard.press('Tab');
        await expect(page.getByRole('button', { name: 'Close evidence' })).toBeFocused();
        await page.keyboard.press('Escape');
        await expect(panel.getByRole('table').getByRole('button').first()).toBeFocused();
      }
    }
  }
  const moving = await page.getByTestId('recorded-workspace').evaluate(
    (e) =>
      [...e.querySelectorAll('*')].filter((el) => {
        const style = getComputedStyle(el);
        return (
          (style.animationName !== 'none' && parseFloat(style.animationDuration) > 0.001) ||
          style.transitionDuration.split(',').some((duration) => parseFloat(duration) > 0.001)
        );
      }).length,
  );
  expect(moving).toBe(0);
});

// Optional captures use the same unmodified local backend recording, never test-route clones.
test('workspace acceptance: genuine local layouts and print media retain limitations and resolvable sources', async ({
  page,
}) => {
  const capture = process.env.CREDITOPS_WORKSPACE_CAPTURE === '1';
  const root = resolve(process.cwd(), '../..');
  const out = resolve(root, 'artifacts/local-validation/workspace-v2');
  const captures: {
    file: string;
    viewport: { width: number; height: number } | null;
    incident: string;
    sourceIds: string[];
    media: string;
  }[] = [];
  if (capture) mkdirSync(out, { recursive: true });
  async function shot(file: string, sourceIds: string[] = [], media = 'screen', fullPage = false) {
    if (!capture) return;
    await page.screenshot({ path: resolve(out, file), fullPage });
    captures.push({
      file,
      viewport: page.viewportSize(),
      incident: 'INC-DEMO-001',
      sourceIds,
      media,
    });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openWorkspace(page);
  await page
    .locator('.recorded-workspace-header')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('desktop-overview.png');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .locator('.recorded-lanes')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('desktop-scrolled-evidence.png');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const row = page
    .getByRole('table', { name: 'Recorded observations' })
    .locator('tr[data-source-id="LOG-001-001"]');
  await row.getByRole('button').click();
  await expect(page.getByRole('dialog')).toContainText('2026-10-09T14:00:00Z');
  await shot('evidence-source-drawer.png', ['LOG-001-001']);
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'Review', exact: true }).click();
  await page
    .locator('.recorded-readable-review')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('review-recorded-reason.png');
  await page.setViewportSize({ width: 390, height: 900 });
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .locator('.recorded-timeline')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('mobile-evidence.png');
  await page.getByRole('tab', { name: 'Review', exact: true }).click();
  await page
    .locator('.recorded-readable-review')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('mobile-review.png');
  await page.setViewportSize({ width: 320, height: 900 });
  await page.getByRole('tab', { name: 'Overview', exact: true }).click();
  await page
    .locator('.recorded-workspace-header')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('mobile-320-overview.png');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page
    .locator('.recorded-evidence-columns')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  await shot('mobile-320-evidence.png');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('tab', { name: 'Handoff', exact: true }).click();
  for (const template of ['technical', 'stakeholder']) {
    await page.getByLabel('Handoff template').selectOption(template);
    await page.getByRole('button', { name: /^(Prepare|Reprepare) draft$/ }).click();
    const preview = page.getByTestId('handoff-preview');
    await expect(preview).toContainText('Synthetic · Recorded · Draft · Human review required');
    await expect(preview).toContainText('Material limitations and uncertainty');
    await expect(preview.locator('.handoff-sources li')).toHaveCount(67);
    await preview.evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
    await shot(
      template + '-handoff.png',
      loadAcceptanceRecording('INC-DEMO-001').evidence.map((e) => e.id),
    );
    const markdown = await page.getByLabel('Prepared Markdown').inputValue();
    if (capture) writeFileSync(resolve(out, template + '-handoff.md'), markdown);
    await page.emulateMedia({ media: 'print' });
    await expectHandoffPrintCanvas(page);
    for (const selector of [
      '.sidebar',
      '.topbar',
      '.recorded-tabs',
      '.handoff-controls',
      '.handoff-markdown',
      '[data-testid="personal-workspace"]',
    ])
      await expect(page.locator(selector)).toBeHidden();
    await expect(preview.locator('.handoff-print-id').first()).toBeVisible();
    if (capture)
      await page.pdf({
        path: resolve(out, template + '-handoff.pdf'),
        format: 'A4',
        printBackground: true,
        preferCSSPageSize: true,
      });
    if (template === 'stakeholder')
      await shot(
        'print-sources-limitations.png',
        loadAcceptanceRecording('INC-DEMO-001').evidence.map((e) => e.id),
        'print',
        true,
      );
    await page.emulateMedia({ media: 'screen' });
    expect(await page.evaluate(() => getComputedStyle(document.documentElement).colorScheme)).toBe(
      'dark',
    );
    expect(
      await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor),
    ).toBe('rgb(11, 17, 27)');
  }
  if (capture) {
    const sha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim();
    const candidateScopeFiles = execFileSync('git', ['diff', '--name-only', 'HEAD'], {
      cwd: root,
      encoding: 'utf8',
    })
      .trim()
      .split(/\r?\n/)
      .filter(Boolean);
    const diff = execFileSync('git', ['diff', 'HEAD', '--', ...candidateScopeFiles], {
      cwd: root,
      encoding: 'utf8',
    });
    writeFileSync(resolve(out, 'task-5-capture-candidate.diff'), diff);
    writeFileSync(
      resolve(out, 'task-5-capture-metadata.json'),
      JSON.stringify(
        {
          capturedAt: new Date().toISOString(),
          candidateBaseSha: sha,
          candidateScopeFiles,
          recordingSourceIds: loadAcceptanceRecording('INC-DEMO-001').evidence.map((e) => e.id),
          candidateDiffSha256: createHash('sha256').update(diff).digest('hex'),
          candidateDiffFile: 'task-5-capture-candidate.diff',
          origin:
            'Actual local keyless showcase UI; packaged recordings unmodified; no routes intercepted in this test.',
          printCheck:
            'Chromium print media and paginated browser-generated A4 PDFs. Native OS preview/dialog and actual clipboard permission not inspected; mocked clipboard tests establish UI paths only.',
          captures,
        },
        null,
        2,
      ),
    );
  }
});

test('final fix: shared business coordinate pointer and keyboard choose exact owners', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const point = page.locator('circle[data-source-id="BUSINESS-001-007"]');
  await point.click();
  const chooser = page.getByRole('group', { name: 'Overlapping recorded sources' });
  await expect(chooser).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  expect(await chooser.getByRole('button').allTextContents()).toEqual([
    'BUSINESS-001-002',
    'BUSINESS-001-007',
  ]);
  await chooser.getByRole('button', { name: 'BUSINESS-001-002', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('BUSINESS-001-002');
  await page.keyboard.press('Escape');
  await point.focus();
  await page.keyboard.press('Enter');
  await expect(chooser).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await chooser.getByRole('button', { name: 'BUSINESS-001-007', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('BUSINESS-001-007');
});
test('final fix: identical metric ties choose owners while distinct values stay direct', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.route('**/api/investigations/*', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch(),
      body = await response.json();
    const source = body.evidence.find((e: { kind: string }) => e.kind === 'metric');
    body.evidence.push(
      { ...structuredClone(source), id: 'TIE-METRIC' },
      {
        ...structuredClone(source),
        id: 'DISTINCT-METRIC',
        data: { ...source.data, value: source.data.value + 5 },
      },
    );
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Metric and unit').selectOption('');
  const point = page.locator('circle[data-source-id="TIE-METRIC"]');
  await point.click();
  const chooser = page.getByRole('group', { name: 'Overlapping recorded sources' });
  await expect(chooser).toBeVisible();
  await expect(chooser.getByRole('button', { name: 'TIE-METRIC', exact: true })).toBeVisible();
  await expect(chooser.getByRole('button', { name: 'DISTINCT-METRIC', exact: true })).toHaveCount(
    0,
  );
  expect(await chooser.getByRole('button').count()).toBe(2);
  await point.focus();
  await page.keyboard.press('Space');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await chooser.getByRole('button', { name: 'TIE-METRIC', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('TIE-METRIC');
  await page.keyboard.press('Escape');
  await page.locator('circle[data-source-id="DISTINCT-METRIC"]').click();
  await expect(page.getByRole('dialog')).toContainText('DISTINCT-METRIC');
});
test('final fix: economic order includes submission and retransmission with literal non-attribution', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-002');
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  await page.getByLabel('Economic order filter').selectOption('ORDER-DEMO-002-001');
  const table = page.getByRole('table', { name: 'Recorded observations' });
  const value = loadAcceptanceRecording('INC-DEMO-002');
  const expected = value.evidence
    .filter(
      (e) =>
        e.kind === 'business_event' &&
        (e.data.economic_order_id ?? e.data.order_id) === 'ORDER-DEMO-002-001',
    )
    .map((e) => e.id)
    .sort();
  expect(
    await table
      .locator('tbody tr[data-source-id^="BUSINESS-"]')
      .evaluateAll((es) => es.map((e) => e.getAttribute('data-source-id')).sort()),
  ).toEqual(expected);
  await expect(table.locator('tr[data-source-id="BUSINESS-002-005"]')).toContainText(
    'order submitted',
  );
  await expect(
    page
      .locator('.recorded-selected-journey li')
      .filter({ has: page.getByRole('button', { name: 'BUSINESS-002-005', exact: true }) }),
  ).toContainText('ORDER_SUBMITTED');
  await expect(table.locator('tr[data-source-id="BUSINESS-002-008"]')).toContainText(
    'fix retransmission',
  );
  await expect(
    page
      .locator('.recorded-selected-journey li')
      .filter({ has: page.getByRole('button', { name: 'BUSINESS-002-008', exact: true }) }),
  ).toContainText('FIX_RETRANSMISSION');
  await expect(table.locator('tr[data-related="false"]').first()).toContainText(
    'Not attributed to this economic order',
  );
  await expect(table.locator('tr[data-source-id="LOG-002-001"]')).toContainText(
    'Not attributed to this economic order',
  );
  await page.getByLabel('Request filter').selectOption('RFQ-DEMO-002-002');
  await expect(page.getByLabel('Economic order filter')).toHaveValue('');
  await expect(table.locator('tr[data-related="false"]').first()).toContainText(
    'Not attributed to this RFQ',
  );
  await page.getByRole('button', { name: 'Reset display filters' }).click();
  await expect(page.getByLabel('Request filter')).toHaveValue('');
  await expect(page.getByLabel('Economic order filter')).toHaveValue('');
});
test('final fix: denied storage clear removes local notes and pins without requests', async ({
  page,
}) => {
  await withRefreshProbe(page, 'memory only', async (probe) => {
    await page.addInitScript(() =>
      Object.defineProperty(window, 'sessionStorage', {
        get() {
          throw Error('denied');
        },
      }),
    );
    await openWorkspace(page);
    await page.getByLabel('Personal note').fill('memory only');
    await page.getByTestId('supporting-evidence').getByRole('button').first().click();
    await page.getByRole('button', { name: 'Pin source', exact: true }).click();
    await page.keyboard.press('Escape');

    // Freeze future shell ticks AND join its response-body/metrics continuation.
    // Workspace visibility and a paused clock alone do not establish that boundary.
    await probe.pause();
    const original = await recordedPresentation(page);
    probe.begin();
    await page.getByTestId('personal-clear').click();
    await expect(page.getByLabel('Personal note')).toHaveValue('');
    await expect(page.getByTestId('personal-workspace')).toContainText('0 / 20');
    await expect(page.getByTestId('personal-workspace')).toContainText(/cleared in memory/i);
    await expect(page.getByTestId('personal-workspace')).toContainText(
      /stored entry.*may reappear/i,
    );

    // Flush the next two animation frames/zero-delay effects while the 2s shell
    // interval remains controlled, then join any action-created API work.
    await page.clock.runFor(32);
    await probe.drain();
    expect(probe.calls).toEqual([]); // Every API path/method, including metrics.
    expect(probe.leaks()).toBe(0);
    expect(await recordedPresentation(page)).toEqual(original);
    probe.end();
    const cursor = (await probe.state()).events.length;
    await page.clock.runFor(2100);
    await probe.drain();
    expect(
      (await probe.state()).events
        .slice(cursor)
        .some((e) => e.phase === 'body_done' && e.path === '/api/metrics/query'),
    ).toBe(true);
    expect(await recordedPresentation(page)).toEqual(original);
    expect(probe.leaks()).toBe(0);
  });
});

test('denied storage clear adds no work to an already-owned refresh tail', async ({ page }) => {
  let holding = false,
    held = false,
    release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await withRefreshProbe(page, 'memory only', async (probe) => {
    await withResetRouteOwner(
      page,
      {
        releaseBarrier: () => release(),
        releaseProbe: () => probe.drain(),
        closeOther: async () => {},
      },
      async (owner) => {
        await owner.route('/api/overview', async (route) => {
          const response = await route.fetch();
          if (holding) {
            holding = false;
            held = true;
            await gate;
          }
          await route.fulfill({ response });
        });
        await page.addInitScript(() =>
          Object.defineProperty(window, 'sessionStorage', {
            get() {
              throw Error('denied');
            },
          }),
        );
        await openWorkspace(page);
        await page.getByLabel('Personal note').fill('memory only');
        await page.getByTestId('supporting-evidence').getByRole('button').first().click();
        await page.getByRole('button', { name: 'Pin source', exact: true }).click();
        await page.keyboard.press('Escape');

        await probe.pause();
        const original = await recordedPresentation(page);
        holding = true;
        await page.clock.runFor(2100);
        await expect.poll(() => held).toBe(true);
        const before = await probe.state();
        const batch = before.events.filter((e) => e.phase === 'refresh_start').at(-1)!.batch;
        expect(
          before.events
            .filter((e) => e.batch === batch && e.phase === 'fetch_start')
            .map((e) => e.path),
        ).toEqual(['/api/overview', '/api/incidents', '/api/services/topology']);
        probe.begin();
        const cursor = before.events.length;
        await page.getByTestId('personal-clear').click();
        await expect(page.getByLabel('Personal note')).toHaveValue('');
        await expect(page.getByTestId('personal-workspace')).toContainText('0 / 20');
        await expect(page.getByTestId('personal-workspace')).toContainText(/cleared in memory/i);
        await expect(page.getByTestId('personal-workspace')).toContainText(
          /stored entry.*may reappear/i,
        );

        // The held real predecessor cannot finish/dispatch metrics until released.
        expect(probe.calls).toEqual([]);
        release();
        await page.clock.runFor(32);
        await probe.drain();
        const after = await probe.state();
        // Positive attribution uses the exact pre-Clear AbortSignal cohort, not a
        // metrics/GET allow-list. Independent Clear requests cannot satisfy this.
        expect(
          after.events
            .slice(cursor)
            .filter((e) => e.phase === 'fetch_start')
            .map(({ phase, path, batch }) => ({ phase, path, batch })),
        ).toEqual([{ phase: 'fetch_start', path: '/api/metrics/query', batch }]);
        expect(probe.calls).toEqual(['/api/metrics/query']);
        expect(probe.leaks()).toBe(0);
        expect(await recordedPresentation(page)).toEqual(original);
        await test.info().attach('safe-pending-clear-refresh-timeline', {
          body: JSON.stringify({ batch, events: after.events }),
          contentType: 'application/json',
        });
      },
    );
  });
});
test('final fix: missing durable identity clear is local and invalid entry remains locked on removal denial', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.route('**/api/investigations/*', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch(),
      body = await response.json();
    delete body.provenance.showcase.source_sha256;
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await page.getByLabel('Personal note').fill('keyless note');
  await page.getByTestId('supporting-evidence').getByRole('button').first().click();
  await page.getByRole('button', { name: 'Pin source', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('personal-workspace')).toContainText('1 / 20');
  await page.getByTestId('personal-clear').click();
  await expect(page.getByLabel('Personal note')).toHaveValue('');
  await expect(page.getByTestId('personal-workspace')).toContainText(/cleared in memory/i);
  await expect(page.getByTestId('personal-workspace')).toContainText('0 / 20');
  await page.unroute('**/api/investigations/*');
  await page.reload();
  await page.getByLabel('Personal note').fill('valid entry');
  await page.evaluate(() => {
    const k = Object.keys(sessionStorage).find((k) => k.startsWith('creditops-workspace:v1:'))!;
    sessionStorage.setItem(k, 'malformed');
  });
  await page.reload();
  await page.evaluate(() => {
    Storage.prototype.removeItem = () => {
      throw Error('denied');
    };
  });
  await page.getByTestId('personal-clear').click();
  await expect(page.getByLabel('Personal note')).toBeDisabled();
  await expect(page.getByTestId('personal-workspace')).toContainText(/invalid/i);
});
test('final fix: shared summary persists across all records and tabs with bounded desktop columns', async ({
  page,
}) => {
  await openWorkspace(page);
  for (const [scenario, id] of examples) {
    if (id !== 'INC-DEMO-001') await page.getByLabel('Incident scenario').selectOption(scenario);
    if (id !== 'INC-DEMO-001')
      await page
        .locator('.scenario-controls')
        .getByRole('button', { name: 'View recorded investigation', exact: true })
        .click();
    await expect(page.getByTestId('recorded-workspace')).toContainText(id);
    const value = loadAcceptanceRecording(id),
      header = page.locator('.recorded-workspace-header');
    for (const name of ['Overview', 'Evidence', 'Review', 'Handoff']) {
      await page.getByRole('tab', { name, exact: true }).click();
      await expect(header).toContainText(value.assessment!.supported_failure_condition!);
      await expect(header).toContainText('Initiating cause unconfirmed');
      await expect(header).toContainText('2 returned RFQs');
      for (const impact of id === 'INC-DEMO-001'
        ? ['stale quotes: 1 RFQ', 'unavailable quotes: 1 RFQ', 'expired RFQ deadlines: 2 RFQs']
        : id === 'INC-DEMO-002'
          ? ['2 economic order identities', 'uncertain acknowledgements: 2 RFQs']
          : ['processing timeouts: 2 RFQs', 'expired RFQ deadlines: 2 RFQs'])
        await expect(header).toContainText(impact);
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.getByRole('tab', { name: 'Overview', exact: true }).click();
  expect(
    await page
      .locator('.recorded-overview-columns')
      .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
  ).toBe(2);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  expect(
    await page
      .locator('.recorded-evidence-columns')
      .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
  ).toBe(2);
  const header = page.locator('.recorded-workspace-header');
  expect(await header.evaluate((e) => getComputedStyle(e).position)).toBe('sticky');
  await page.locator('.recorded-lanes').evaluate((e) => e.scrollIntoView({ block: 'start' }));
  expect((await header.boundingBox())!.height).toBeLessThan(360);
  expect((await header.boundingBox())!.y).toBeGreaterThanOrEqual(0);
  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await header.evaluate((e) => getComputedStyle(e).position)).toBe('static');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});

test('final fix: desktop sticky composition stacks at mobile', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openWorkspace(page);
  const header = page.locator('.recorded-workspace-header');
  expect(await header.evaluate((e) => getComputedStyle(e).position)).toBe('sticky');
  expect(
    await page
      .locator('.recorded-overview-columns')
      .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
  ).toBe(2);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  expect(
    await page
      .locator('.recorded-evidence-columns')
      .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
  ).toBe(2);
  await page
    .locator('.recorded-lanes')
    .evaluate((e) => e.scrollIntoView({ block: 'start', behavior: 'instant' }));
  const bounds = (await header.boundingBox())!;
  expect(bounds.y).toBeGreaterThanOrEqual(0);
  expect(bounds.y).toBeLessThanOrEqual(76);
  expect(bounds.height).toBeLessThan(360);
  for (const width of [768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await header.evaluate((e) => getComputedStyle(e).position)).toBe('static');
    expect(
      await page
        .locator('.recorded-evidence-columns')
        .evaluate((e) => getComputedStyle(e).gridTemplateColumns.split(' ').length),
    ).toBe(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});

test('final fix: timestamped context keeps outside and invalid annotations inert with exact returned references', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('recorded-workspace')).toContainText('INC-DEMO-003');
  await page.route('**/api/investigations/*', async (route) => {
    if (route.request().method() !== 'GET') return route.continue();
    const response = await route.fetch(),
      body = await response.json();
    const owner = body.evidence.find((e: { kind: string }) => e.kind === 'incident');
    owner.data.timeline.push(
      {
        timestamp: '2026-10-09T16:00:00Z',
        label: 'Outside coverage context',
        evidence_ids: ['LOG-003-001', 'CONTEXT-MISSING'],
      },
      {
        timestamp: 'invalid-time',
        label: 'Invalid annotation time',
        evidence_ids: ['CONTEXT-INVALID-MISSING'],
      },
    );
    await route.fulfill({ response, json: body });
  });
  await page.reload();
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const lookups: string[] = [];
  page.on('request', (r) => {
    if (/\/api\/evidence\//.test(r.url())) lookups.push(r.url());
  });
  const annotations = page.locator('.recorded-context-annotations');
  await expect(annotations).toContainText('Alert threshold crossed');
  await expect(annotations).toContainText('2026-10-09T14:00:00Z');
  await expect(annotations).toContainText('DEPLOY-003-001');
  const outside = annotations
    .locator(':scope > li')
    .filter({ hasText: 'Outside coverage context' });
  await expect(outside).toContainText('2026-10-09T16:00:00Z');
  await expect(outside).toContainText('Outside returned-sample coverage');
  await expect(outside).toContainText('Referenced in context; source not returned');
  await expect(outside.getByRole('button', { name: 'CONTEXT-MISSING', exact: true })).toHaveCount(
    0,
  );
  await expect(annotations).toContainText('Invalid recorded annotation timestamp');
  await expect(page.locator('circle[data-source-id="CONTEXT-MISSING"]')).toHaveCount(0);
  await outside.getByRole('button', { name: 'LOG-003-001', exact: true }).click();
  await expect(page.getByRole('dialog')).toContainText('LOG-003-001');
  await page.keyboard.press('Escape');
  expect(lookups).toEqual([]);
});

async function expectUsableViewport(locator: import('@playwright/test').Locator) {
  await test.info().attach('viewport-before-check', {
    body: JSON.stringify(
      await locator.evaluate((element) => {
        const box = element.getBoundingClientRect();
        const header = document
          .querySelector('.recorded-workspace-header')
          ?.getBoundingClientRect();
        return {
          target: element.getAttribute('aria-label') ?? element.textContent,
          bounds: { top: box.top, bottom: box.bottom, left: box.left, right: box.right },
          viewport: { width: innerWidth, height: innerHeight },
          header: header ? { top: header.top, bottom: header.bottom, height: header.height } : null,
          centerHit: document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
            ?.outerHTML,
        };
      }),
      null,
      2,
    ),
    contentType: 'application/json',
  });
  await expect
    .poll(() =>
      locator.evaluate((element) => {
        const box = element.getBoundingClientRect();
        const inset = Math.min(4, box.width / 4, box.height / 4);
        const points = [
          [box.left + inset, box.top + inset],
          [box.left + box.width / 2, box.top + box.height / 2],
          [box.right - inset, box.bottom - inset],
        ];
        return {
          inViewport:
            box.width > 0 &&
            box.height > 0 &&
            box.top >= 0 &&
            box.bottom <= innerHeight &&
            box.left >= 0 &&
            box.right <= innerWidth,
          unobscured: points.every(([x, y]) => {
            const hit = document.elementFromPoint(x, y);
            return hit !== null && (hit === element || element.contains(hit));
          }),
          bounds: { top: box.top, bottom: box.bottom, left: box.left, right: box.right },
          viewport: { width: innerWidth, height: innerHeight },
        };
      }),
    )
    .toMatchObject({ inViewport: true, unobscured: true });
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 1024, height: 768 },
]) {
  test(
    'header qualification: sections remain reachable after scroll at ' + viewport.width,
    async ({ page }) => {
      await page.setViewportSize(viewport);
      await openWorkspace(page);
      const workspace = page.getByTestId('recorded-workspace');
      await expect(workspace).toContainText('Synthetic');
      await expect(workspace).toContainText('Initiating cause unconfirmed');
      for (const name of ['Evidence', 'Review', 'Handoff'] as const) {
        await workspace.locator('[role="tabpanel"]:not([hidden])').evaluate((panel) => {
          const bottom = panel.getBoundingClientRect().bottom + scrollY;
          window.scrollTo({ top: bottom - innerHeight / 2, behavior: 'instant' });
        });
        const tab = page.getByRole('tab', { name, exact: true });
        // Use the same native scrolling path as a normal Playwright pointer action.
        await tab.scrollIntoViewIfNeeded();
        await expectUsableViewport(tab);
        await page.screenshot({ path: test.info().outputPath('native-scroll-' + name + '.png') });
        await tab.click();
        await expect(tab).toHaveAttribute('aria-selected', 'true');
        const panel = page.getByRole('tabpanel', { name, exact: true });
        await expect(panel).toBeVisible();
        await tab.focus();
        await page.keyboard.press('Tab');
        await expect(panel).toBeFocused();
        await page.keyboard.press('Tab');
        const control = panel.locator('button, select, input, summary, [tabindex="0"]').first();
        await expect(control).toBeFocused();
        await expectUsableViewport(control);
        await page.screenshot({
          path: test.info().outputPath('active-' + name + '-focused-control.png'),
        });
        if ((await control.getAttribute('aria-label')) === 'UTC end')
          await page.screenshot({ path: test.info().outputPath('keyboard-UTC-end.png') });
      }
    },
  );

  test(
    'header qualification: keyboard evidence filters remain unobscured at ' + viewport.width,
    async ({ page }) => {
      await page.setViewportSize(viewport);
      await openWorkspace(page);
      const evidence = page.getByRole('tab', { name: 'Evidence', exact: true });
      await evidence.click();
      await page.getByTestId('recorded-context').evaluate((element) => {
        window.scrollTo({
          top: element.getBoundingClientRect().top + scrollY,
          behavior: 'instant',
        });
      });
      // The deep-scroll source owns focus before keyboard focus actually moves back to the tab.
      await page.getByTestId('recorded-context').getByRole('button').first().focus();
      await evidence.focus();
      await expectUsableViewport(evidence);
      await page.keyboard.press('Tab');
      await expect(page.getByRole('tabpanel', { name: 'Evidence', exact: true })).toBeFocused();
      for (const control of [
        page.getByLabel('Service filter'),
        page.getByLabel('Metric and unit'),
        page.getByLabel('Request filter'),
        page.getByLabel('Economic order filter'),
        page.getByLabel('UTC start'),
        page.getByLabel('UTC end'),
        page.getByRole('button', { name: 'Reset display filters', exact: true }),
      ]) {
        await page.keyboard.press('Tab');
        await expect(control).toBeFocused();
        await expectUsableViewport(control);
        if ((await control.getAttribute('aria-label')) === 'UTC end')
          await page.screenshot({ path: test.info().outputPath('keyboard-UTC-end.png') });
      }
    },
  );
}

for (const viewport of [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
  { width: 320, height: 740 },
]) {
  test(
    'header qualification: exact Reveal and drawer return remain usable at ' + viewport.width,
    async ({ page }) => {
      await page.setViewportSize(viewport);
      const errors: string[] = [];
      page.on('pageerror', (error) => errors.push(error.message));
      await openWorkspace(page);
      const evidence = page.getByRole('tab', { name: 'Evidence', exact: true });
      await evidence.click();
      const sourceId = 'LOG-001-001';
      const row = page
        .getByRole('table', { name: 'Recorded observations' })
        .locator('tr[data-source-id="LOG-001-001"]');
      const citation = row.getByRole('button', { name: sourceId, exact: true });
      await citation.click();
      const dialog = page.getByRole('dialog', { name: 'Evidence details' });
      const close = dialog.getByRole('button', { name: 'Close evidence', exact: true });
      await expect(dialog.getByRole('heading', { name: sourceId, exact: true })).toBeVisible();
      await expect(close).toBeFocused();
      await expectUsableViewport(close);
      await page.keyboard.press('Escape');
      await expect(citation).toBeFocused();
      await expectUsableViewport(citation);

      await page.getByLabel('Service filter').selectOption('fix-gateway');
      await expect(row).toHaveCount(0);
      const selection = page.getByTestId('selected-source-state');
      await expect(selection).toContainText(sourceId);
      await expect(selection).toContainText('Hidden by filters');
      const trigger = selection.getByRole('button', { name: 'Open selected source', exact: true });
      await trigger.click();
      await expect(dialog.getByRole('heading', { name: sourceId, exact: true })).toBeVisible();
      await expect(close).toBeFocused();
      await expect(
        dialog.getByRole('button', { name: 'Reveal source', exact: true }),
      ).toBeVisible();
      await expect(
        dialog.getByRole('button', { name: 'Reveal source', exact: true }),
      ).toBeEnabled();
      await page.keyboard.press('Tab');
      const reveal = dialog.getByRole('button', { name: 'Reveal source', exact: true });
      await expect(reveal).toBeFocused();
      await expectUsableViewport(reveal);
      await page.keyboard.press('Enter');
      await expect(dialog).not.toContainText('Hidden by filters');
      await expect(close).toBeFocused();
      await page.keyboard.press('Escape');
      // Reveal returns focus to its exact visible source; ordinary close above keeps its trigger.
      await expect(citation).toBeFocused();
      await expectUsableViewport(citation);
      await expect(row).toHaveAttribute('data-selected', 'true');
      await page.screenshot({ path: test.info().outputPath('revealed-exact-source.png') });
      await expect(selection).toContainText(sourceId);

      await test.info().attach('revealed-source-viewport', {
        body: JSON.stringify(
          await page
            .locator(
              '[data-testid="timeline-marker"][data-source-id="LOG-001-001"], ' +
                'table[aria-label="Recorded observations"] tr[data-source-id="LOG-001-001"] button',
            )
            .evaluateAll((elements) =>
              elements.map((element) => {
                const box = element.getBoundingClientRect();
                return {
                  sourceId: element.closest('[data-source-id]')?.getAttribute('data-source-id'),
                  bounds: { top: box.top, bottom: box.bottom, left: box.left, right: box.right },
                  viewport: { width: innerWidth, height: innerHeight },
                };
              }),
            ),
          null,
          2,
        ),
        contentType: 'application/json',
      });
      // Reveal must leave an actual exact source representation in a usable viewport,
      // not only retain its ID in the selection summary.
      const representations = page.locator(
        '[data-testid="timeline-marker"][data-source-id="LOG-001-001"], ' +
          'table[aria-label="Recorded observations"] tr[data-source-id="LOG-001-001"] button',
      );
      await expect
        .poll(() =>
          representations.evaluateAll((elements) =>
            elements.some((element) => {
              const box = element.getBoundingClientRect();
              const hit = document.elementFromPoint(
                box.left + box.width / 2,
                box.top + box.height / 2,
              );
              return (
                box.width > 0 &&
                box.height > 0 &&
                box.top >= 0 &&
                box.bottom <= innerHeight &&
                box.left >= 0 &&
                box.right <= innerWidth &&
                hit !== null &&
                (hit === element || element.contains(hit))
              );
            }),
          ),
        )
        .toBe(true);

      // A normal scroll can reach lower evidence and return to every section on mobile.
      if (viewport.width <= 768) {
        const contextSource = page.getByTestId('recorded-context').getByRole('button').first();
        await contextSource.scrollIntoViewIfNeeded();
        await expectUsableViewport(contextSource);
        for (const name of ['Review', 'Handoff', 'Evidence'] as const) {
          const tab = page.getByRole('tab', { name, exact: true });
          await tab.scrollIntoViewIfNeeded();
          await expectUsableViewport(tab);
          await page.screenshot({ path: test.info().outputPath('native-scroll-' + name + '.png') });
          await tab.click();
          await expect(tab).toHaveAttribute('aria-selected', 'true');
        }
      }
      expect(errors).toEqual([]);
    },
  );
}

test('header qualification: personal note focus remains unobscured at 1024', async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await openWorkspace(page);
  const note = page.getByLabel('Personal note', { exact: true });
  await expect(note).not.toBeFocused();
  await note.focus();
  await expect(note).toBeFocused();
  await expectUsableViewport(note);
  await page.screenshot({ path: test.info().outputPath('focused-personal-note.png') });
});

test('header qualification: inline Reveal brings its exact source into view at 1024', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 768 });
  await openWorkspace(page);
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const row = page
    .getByRole('table', { name: 'Recorded observations' })
    .locator('tr[data-source-id="LOG-001-001"]');
  const citation = row.getByRole('button', { name: 'LOG-001-001', exact: true });
  await citation.click();
  await page.keyboard.press('Escape');
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  await expect(row).toHaveCount(0);
  const selection = page.getByTestId('selected-source-state');
  await expect(selection).toContainText('LOG-001-001');
  await expect(selection).toContainText('Hidden by filters');
  await selection.getByRole('button', { name: 'Reveal source', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Evidence details' })).toHaveCount(0);
  await expect(row).toHaveAttribute('data-selected', 'true');
  await expectUsableViewport(citation);
  await expect(citation).toBeFocused();
  await page.screenshot({ path: test.info().outputPath('inline-revealed-exact-source.png') });
});

// Focus readiness and native traversal use the same public showcase profile as this suite.
async function expectRevealKeyboardFocus(control: import('@playwright/test').Locator) {
  await expect(control).toBeFocused();
  await expect(control).toBeVisible();
  const state = await control.evaluate((element) => {
    const bounds = element.getBoundingClientRect();
    return {
      focusVisible: element.matches(':focus-visible'),
      left: bounds.left,
      right: bounds.right,
      top: bounds.top,
      bottom: bounds.bottom,
      width: innerWidth,
      height: innerHeight,
    };
  });
  expect(state.focusVisible).toBe(true);
  expect(state.left).toBeGreaterThanOrEqual(0);
  expect(state.top).toBeGreaterThanOrEqual(0);
  expect(state.right).toBeLessThanOrEqual(state.width);
  expect(state.bottom).toBeLessThanOrEqual(state.height);
}

async function openRevealFocusHiddenSource(page: import('@playwright/test').Page) {
  await page.getByRole('tab', { name: 'Evidence', exact: true }).click();
  const source = page
    .getByRole('table', { name: 'Recorded observations' })
    .locator('tr[data-source-id="LOG-001-001"]')
    .getByRole('button', { name: 'LOG-001-001', exact: true });
  await source.click();
  await page.getByRole('button', { name: 'Close evidence' }).click();
  await page.getByLabel('Service filter').selectOption('fix-gateway');
  const trigger = page
    .getByTestId('selected-source-state')
    .getByRole('button', { name: 'Open selected source', exact: true });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Evidence details' });
  const close = dialog.getByRole('button', { name: 'Close evidence', exact: true });
  const reveal = dialog.getByRole('button', { name: 'Reveal source', exact: true });
  const pin = dialog.getByRole('button', { name: 'Pin source', exact: true });
  await expect(close).toBeFocused();
  await expect(reveal).toBeVisible();
  await expect(reveal).toBeEnabled();
  return { source, trigger, dialog, close, reveal, pin };
}

for (const width of [1440, 390]) {
  test(`ready drawer keyboard survives refresh and restores exact source at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.clock.install();
    await openWorkspace(page);
    await expect(page.getByLabel('Personal note')).toBeEnabled();
    const { source, dialog, close, reveal, pin } = await openRevealFocusHiddenSource(page);
    await page.keyboard.press('Tab');
    await expectRevealKeyboardFocus(reveal);
    // A completed ordinary Console refresh must not reinitialize an open drawer's focus.
    const refreshed = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === '/api/metrics/query' && response.status() === 200,
    );
    await page.clock.runFor(2100);
    await refreshed;
    await expectRevealKeyboardFocus(reveal);
    await expect(dialog.getByRole('heading', { name: 'LOG-001-001', exact: true })).toBeVisible();
    await page.keyboard.press('Enter');
    await expect(reveal).toHaveCount(0);
    await expect(close).toBeFocused();
    await expect(pin).toBeEnabled();
    await page.keyboard.press('Tab');
    await expect(pin).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(pin).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(close).toBeFocused();
    await page.keyboard.press('Escape');
    await expectRevealKeyboardFocus(source);
    // Reopening an already available source preserves ordinary trigger restoration.
    await source.click();
    await expect(close).toBeFocused();
    await expect(pin).toBeEnabled();
    await page.keyboard.press('Tab');
    await expect(pin).toBeFocused();
    await page.keyboard.press('Escape');
    await expectRevealKeyboardFocus(source);
  });
}

test('disabled pin is excluded from native drawer traversal before and after Reveal', async ({
  page,
}) => {
  await openWorkspace(page);
  await expect(page.getByLabel('Personal note')).toBeEnabled();
  await page.getByLabel('Personal note').fill('create a scoped personal entry');
  await page.evaluate(() => {
    const key = Object.keys(sessionStorage).find((value) =>
      value.startsWith('creditops-workspace:v1:'),
    )!;
    sessionStorage.setItem(key, 'malformed');
  });
  await page.reload();
  await expect(page.getByTestId('personal-workspace')).toContainText(/invalid/i);
  const { source, close, reveal, pin } = await openRevealFocusHiddenSource(page);
  await expect(pin).toBeDisabled();
  await page.keyboard.press('Tab');
  await expectRevealKeyboardFocus(reveal);
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expectRevealKeyboardFocus(reveal);
  await page.keyboard.press('Enter');
  await expect(reveal).toHaveCount(0);
  await expect(close).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(close).toBeFocused();
  await page.keyboard.press('Escape');
  await expectRevealKeyboardFocus(source);
});

// Selection is application control; fixtures are the recording/evidence oracle.
test('scenario selection: unloaded selection never falls back and only View creates a recording', async ({
  page,
}) => {
  await page.goto('/');
  await page
    .getByTestId('recorded-example')
    .and(page.locator('[data-scenario="db-pool-exhaustion"]'))
    .click();
  await page.getByTestId('view-recorded-investigation').click();
  await expect(page.getByTestId('failure-domain')).toHaveText(/database/);
  const mutations: string[] = [];
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname.startsWith('/api/'))
      mutations.push(new URL(request.url()).pathname);
  });
  const selector = page.getByLabel('Incident scenario');
  await selector.focus();
  await page.keyboard.press('Home');
  await page.keyboard.press('Enter');
  await expect(selector).toHaveValue('kafka-pricing-lag');
  await expect(page.getByTestId('scenario-selection-state')).toContainText('not loaded');
  await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Reset Scenario', exact: true })).toBeDisabled();
  expect(mutations).toEqual([]);
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('failure-domain')).toHaveText(/pricing-service.*Kafka/i);
  expect(mutations).toEqual(['/api/demo/scenarios/kafka-pricing-lag/run', '/api/investigations']);
});

test('scenario selection: all six loaded transitions retain exact recording, sources, review, notes and handoff', async ({
  page,
}) => {
  await openWorkspace(page);
  for (const [scenario, id, domain] of examples) {
    await page.getByLabel('Incident scenario').selectOption(scenario);
    if (id !== 'INC-DEMO-001')
      await page
        .locator('.scenario-controls')
        .getByRole('button', { name: 'View recorded investigation', exact: true })
        .click();
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    await page.getByLabel('Personal note').fill('local note for ' + id);
  }
  const mutations: string[] = [],
    diagnostics: string[] = [];
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname;
    if (request.method() === 'POST' && path.startsWith('/api/')) mutations.push(path);
    if (path.startsWith('/api/diagnostics/')) diagnostics.push(path);
  });
  // Starting at 003: 3→1, 1→2, 2→1, 1→3, 3→2, 2→3.
  for (const index of [0, 1, 0, 2, 1, 2]) {
    const [scenario, id, domain] = examples[index];
    const fixture = loadAcceptanceRecording(id);
    await page.getByLabel('Incident scenario').selectOption(scenario);
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    const workspace = page.getByTestId('recorded-workspace');
    await expect(workspace.locator('.recorded-workspace-header')).toContainText(id);
    await expect(page.getByLabel('Personal note')).toHaveValue('local note for ' + id);
    const citation = page.getByTestId('supporting-evidence').getByRole('button').first();
    const sourceId = await citation.innerText();
    const source = fixture.evidence.find((row) => row.id === sourceId);
    expect(source).toBeTruthy();
    await citation.click();
    const dialog = page.getByRole('dialog', { name: 'Evidence details' });
    await expect(dialog).toContainText(source!.id);
    await expect(dialog).toContainText(source!.timestamp.slice(0, 10));
    await page.keyboard.press('Escape');
    await page.getByRole('tab', { name: 'Review', exact: true }).click();
    await expect(page.getByRole('table', { name: 'Recorded field comparison' })).toBeVisible();
    await page.getByRole('tab', { name: 'Handoff', exact: true }).click();
    await page.getByRole('button', { name: 'Prepare draft', exact: true }).click();
    await expect(page.getByTestId('handoff-preview')).toContainText('Incident: ' + id);
    const ids = await page
      .getByTestId('handoff-preview')
      .locator('[data-source-id]')
      .evaluateAll((rows) => rows.map((row) => row.getAttribute('data-source-id')));
    expect(ids.length).toBeGreaterThan(0);
    expect(ids.every((sourceId) => fixture.evidence.some((row) => row.id === sourceId))).toBe(true);
  }
  expect(mutations).toEqual([]);
  expect(diagnostics).toEqual([]);
  await page.reload();
  await expect(page.getByTestId('failure-domain')).toHaveText(examples[2][2]);
  await page.goto('/investigator');
  await expect(page.getByTestId('failure-domain')).toHaveText(examples[2][2]);
});

test('scenario selection: pending and mismatched restoration never display current or unrelated evidence', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion');
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.getByTestId('failure-domain')).toHaveText(/database/);
  const saved = await page.evaluate(() =>
    localStorage.getItem('creditops-investigation:v1:INC-DEMO-001'),
  );
  let release!: () => void, reached!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const started = new Promise<void>((resolve) => {
    reached = resolve;
  });
  await withResetRouteOwner(
    page,
    { releaseBarrier: () => release(), releaseProbe: async () => {}, closeOther: async () => {} },
    async (owner) => {
      await owner.route('/api/investigations/' + saved, async (route) => {
        const response = await route.fetch();
        reached();
        await gate;
        const value = await response.json();
        // A real response with a deliberately incorrect incident reference must be rejected.
        await route.fulfill({ response, json: { ...value, incident_id: 'INC-DEMO-003' } });
      });
      await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
      await started;
      await expect(page.getByTestId('scenario-selection-state')).toContainText('Restoring');
      await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
      await expect(page.getByTestId('incident-detail')).toHaveCount(0);
      release();
      await expect(page.locator('.error-banner[role=alert]')).toContainText('unexpected incident');
      await expect(page.getByTestId('scenario-selection-state')).toContainText('not loaded');
      await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
    },
  );
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await page.evaluate(() => {
    const native = window.fetch;
    window.fetch = (input, init) => {
      const path = new URL(String(input), location.href).pathname;
      if (path === '/api/demo/scenarios/fix-connectivity/run')
        return Promise.reject(new TypeError('Controlled loading failure'));
      return native(input, init);
    };
  });
  await page
    .locator('.scenario-controls')
    .getByRole('button', { name: 'View recorded investigation', exact: true })
    .click();
  await expect(page.locator('.error-banner[role=alert]')).toBeVisible();
  await expect(page.getByTestId('scenario-selection-state')).toContainText('not loaded');
  await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
});

for (const width of [320, 390, 768, 1024, 1440, 1920]) {
  test(`scenario controls: readable native selection and keyboard actions at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await openWorkspace(page);
    const selector = page.getByLabel('Incident scenario');
    const fullLabel = page.getByTestId('selected-scenario-title');
    const options = await selector.locator('option').allTextContents();
    await expect(fullLabel).toHaveText(options[0]);
    await selector.focus();
    await page.keyboard.press('Space');
    await page.keyboard.press('End');
    await page.keyboard.press('Enter');
    await expect(fullLabel).toHaveText(options[2]);
    await expect(selector).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(
      page
        .locator('.scenario-actions')
        .getByRole('button', { name: 'View recorded investigation', exact: true }),
    ).toBeFocused();
    for (const control of await page
      .locator('.scenario-controls select, .scenario-controls button')
      .all()) {
      const bounds = await control.boundingBox();
      expect(bounds).not.toBeNull();
      expect(bounds!.width).toBeGreaterThanOrEqual(Math.min(width - 60, 280));
      expect(bounds!.height).toBeGreaterThanOrEqual(44);
      expect(bounds!.x).toBeGreaterThanOrEqual(0);
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await test
      .info()
      .attach(`controls-${width}`, { body: await page.screenshot(), contentType: 'image/png' });
  });
}

test('scenario selection: missing deep link cannot restore a different loaded incident', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.goto('/incidents/INC-DEMO-003');
  await expect(page.getByTestId('scenario-selection-state')).toContainText('not loaded');
  await expect(page.getByRole('main')).toContainText('Requested incident INC-DEMO-003');
  await expect(page.getByTestId('recorded-workspace')).toHaveCount(0);
  // An explicit selection resolves the unavailable URL target without creating anything.
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.getByTestId('failure-domain')).toHaveText(examples[0][2]);
});

test('scenario selection: initial profile and saved restore cannot expose current simulation details', async ({
  page,
}) => {
  await openWorkspace(page);
  let release!: () => void, reached!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const started = new Promise<void>((resolve) => {
    reached = resolve;
  });
  const liveImpact: string[] = [];
  page.on('request', (request) => {
    if (/\/api\/incidents\/.*\/business-impact/.test(request.url()))
      liveImpact.push(new URL(request.url()).pathname);
  });
  await withResetRouteOwner(
    page,
    { releaseBarrier: () => release(), releaseProbe: async () => {}, closeOther: async () => {} },
    async (owner) => {
      await owner.route('/api/evaluations/latest', async (route) => {
        const response = await route.fetch();
        reached();
        await gate;
        await route.fulfill({ response });
      });
      const incidents = page.waitForResponse(
        (response) => new URL(response.url()).pathname === '/api/incidents',
      );
      await page.reload();
      await started;
      await incidents;
      await expect(page.getByTestId('scenario-selection-state')).toContainText(
        'application profile',
      );
      await expect(page.getByTestId('incident-detail')).toHaveCount(0);
      expect(liveImpact).toEqual([]);
      release();
      await expect(page.getByTestId('failure-domain')).toHaveText(examples[0][2]);
    },
  );
  expect(liveImpact).toEqual([]);
});

test.describe('scenario controls: 200 percent reflow', () => {
  // 1440×900 physical pixels at 200%: 720×450 CSS px, DPR 2.
  // This checks layout reflow, not native browser-menu zoom UI.
  test.use({ viewport: { width: 720, height: 450 }, deviceScaleFactor: 2 });
  test('selector, actions and four workspace tabs remain usable', async ({ page }) => {
    await openWorkspace(page);
    const selector = page.getByLabel('Incident scenario');
    const option = await selector.locator('option:checked').textContent();
    await expect(page.getByTestId('selected-scenario-title')).toHaveText(option!);
    await selector.focus();
    await page.keyboard.press('Tab');
    await expect(
      page
        .locator('.scenario-actions')
        .getByRole('button', { name: 'View recorded investigation', exact: true }),
    ).toBeFocused();
    for (const tab of ['Overview', 'Evidence', 'Review', 'Handoff']) {
      await page.getByRole('tab', { name: tab, exact: true }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(720);
    }
    await page.getByLabel('Incident scenario').scrollIntoViewIfNeeded();
    await test.info().attach('controls-200-percent-reflow', {
      body: await page.screenshot(),
      contentType: 'image/png',
    });
    expect(await page.evaluate(() => devicePixelRatio)).toBe(2);
  });
});

test('responsive companion: observability window keeps the full selected ID and title readable', async ({
  page,
}) => {
  await openWorkspace(page);
  await page.goto('/observability');
  const select = page.getByLabel('Incident time window');
  await expect(select).toHaveValue('INC-DEMO-001');
  const label = await select.locator('option:checked').textContent();
  expect(label).toContain('INC-DEMO-001');
  for (const width of [320, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.getByTestId('selected-window-title')).toHaveText(label!);
    const geometry = await select.evaluate((el) => {
      const b = el.getBoundingClientRect();
      return {
        width: b.width,
        height: b.height,
        left: b.left,
        right: b.right,
        fontSize: parseFloat(getComputedStyle(el).fontSize),
      };
    });
    expect(geometry.fontSize).toBeGreaterThanOrEqual(14);
    expect(geometry.height).toBeGreaterThanOrEqual(44);
    expect(geometry.width).toBeGreaterThanOrEqual(Math.min(width - 60, 280));
    expect(geometry.left).toBeGreaterThanOrEqual(0);
    expect(geometry.right).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(width);
    await select.focus();
    await expect(select).toBeFocused();
    await test
      .info()
      .attach(`window-control-${width}`, {
        body: await page.screenshot(),
        contentType: 'image/png',
      });
  }
});
