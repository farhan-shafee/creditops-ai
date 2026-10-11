import { test, expect } from '@playwright/test';

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
  await expect(trigger).toBeFocused();
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
test('workspace notes: denied storage keeps edits in memory with refresh warning', async ({
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
test('workspace notes: malformed entry has current-record clear option', async ({ page }) => {
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
test('workspace notes: full storage warns while successful late reset clears captured scope only', async ({
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
  // Inject a late event to exercise captured scope while the clock locks selection.
  await page.getByLabel('Incident scenario').selectOption('db-pool-exhaustion', { force: true });
  release();
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
test('workspace notes: successful reset discloses removal denial and retries captured personal cleanup only', async ({
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
