import { test, expect } from '@playwright/test';

test('overview describes synthetic operations and the safety boundary', async ({ page }) => {
  await page.goto('/');
  await expect(
    page.getByRole('heading', { name: 'AI-assisted incident intelligence', exact: false }),
  ).toBeVisible();
  await expect(page.getByRole('button', { name: 'Run Incident Demo', exact: true })).toBeVisible();
  await expect(
    page.getByText(
      'CreditOps AI is an independent portfolio project using entirely synthetic data.',
      { exact: false },
    ),
  ).toBeVisible();
});

for (const [scenario, domain] of [
  ['kafka-pricing-lag', /pricing-service.*Kafka consumer backlog/i],
  ['fix-connectivity', /FIX connectivity.*session instability/i],
  ['db-pool-exhaustion', /database connection pool exhaustion/i],
] as const) {
  test(`${scenario}: real replay pipeline streams findings, evidence opens, reset clears incident`, async ({
    page,
  }) => {
    await page.goto('/incidents');
    await page.getByLabel('Incident scenario').selectOption(scenario);
    await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
    await expect(page.getByTestId('incident-detail')).toBeVisible();
    await expect(page.getByText('Simulated clock', { exact: false }).first()).toBeVisible();
    await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
    await expect(page.getByTestId('assessment')).toBeVisible();
    await expect(page.getByTestId('failure-domain')).toHaveText(domain);
    await expect(
      page.getByText('Replay · deterministic provider', { exact: true }).first(),
    ).toBeVisible();
    await expect(page.getByTestId('investigation-step').first()).toBeVisible();
    const citation = page.getByTestId('supporting-evidence').getByRole('button').first();
    const evidenceId = await citation.innerText();
    await citation.click();
    await expect(page.getByRole('dialog', { name: 'Evidence details' })).toBeVisible();
    await expect(page.getByRole('dialog').getByText(evidenceId, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Close evidence' }).click();
    await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
    await expect(page.getByTestId('incident-detail')).not.toBeVisible();
  });
}

test('console pages remain usable with no horizontal overflow at all target widths', async ({
  page,
}) => {
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of [
      '/',
      '/incidents',
      '/live-operations',
      '/investigator',
      '/observability',
      '/service-map',
      '/evaluations',
      '/architecture',
      '/about',
      '/runbooks',
      '/history',
    ]) {
      await page.goto(path);
      await expect(page.getByRole('main')).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth,
      );
      expect(overflow, `${path} overflows at ${width}`).toBe(false);
    }
  }
});

test('mobile navigation keeps keyboard focus inside the menu and closes with Escape', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const open = page.getByRole('button', { name: 'Open navigation' });
  await open.click();
  const menu = page.getByRole('dialog', { name: 'Main navigation' });
  await expect(menu).toBeVisible();
  await expect(page.getByRole('button', { name: 'Close navigation' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(menu.getByRole('link', { name: 'About', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).not.toBeVisible();
  await expect(open).toBeFocused();
});

test('completed investigation survives reload and opens in the investigator workspace', async ({
  page,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  await expect(page.getByTestId('assessment')).toBeVisible();
  const domain = await page.getByTestId('failure-domain').innerText();
  await page.reload();
  await expect(page.getByTestId('failure-domain')).toHaveText(domain);
  await page.getByRole('link', { name: 'AI Investigator', exact: true }).click();
  await expect(page.getByTestId('failure-domain')).toHaveText(domain);
});

test('a different browser session does not inherit an active demo incident', async ({
  page,
  browser,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByTestId('incident-detail')).toBeVisible();
  const isolated = await browser.newContext();
  const secondPage = await isolated.newPage();
  await secondPage.goto(new URL('/incidents', page.url()).toString());
  await expect(secondPage.getByText('API connected', { exact: true })).toBeVisible();
  await expect(secondPage.getByTestId('incident-detail')).not.toBeVisible();
  await expect(
    secondPage.getByRole('heading', { name: 'Your investigation starts with a signal' }),
  ).toBeVisible();
  await isolated.close();
});

test('a truncated investigation stream produces an actionable failure without an invented assessment', async ({
  page,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await page.route('**/api/investigations/*/events', (route) =>
    route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: ': connection closed\n\n',
    }),
  );
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'Investigation stream ended before completion',
  );
  await expect(page.getByTestId('assessment')).not.toBeVisible();
  await expect(
    page.getByRole('button', { name: 'View recorded investigation', exact: true }),
  ).toBeEnabled();
});

test('the console recovers when its initial scenario request is temporarily unavailable', async ({
  page,
}) => {
  let unavailable = true;
  await page.route('**/api/scenarios', (route) =>
    unavailable
      ? route.fulfill({
          status: 503,
          body: JSON.stringify({ detail: 'Temporary synthetic test outage' }),
          contentType: 'application/json',
        })
      : route.continue(),
  );
  await page.goto('/incidents');
  await expect(page.getByRole('main').getByRole('alert')).toContainText(
    'Temporary synthetic test outage',
  );
  unavailable = false;
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
});

test('switching incidents during a real pending stream cannot attach the old assessment to the new incident', async ({
  page,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-001');
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-002');
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-001');
  let release!: () => void;
  let requested!: () => void;
  let delivered!: () => void;
  const released = new Promise<void>((resolve) => {
    release = resolve;
  });
  const streamRequested = new Promise<void>((resolve) => {
    requested = resolve;
  });
  const streamDelivered = new Promise<void>((resolve) => {
    delivered = resolve;
  });
  await page.route('**/api/investigations/*/events', async (route) => {
    requested();
    const response = await route.fetch();
    await released;
    await route.fulfill({ response }).catch(() => {});
    delivered();
  });
  const investigationRequest = page.waitForRequest(
    (request) => request.method() === 'POST' && request.url().endsWith('/api/investigations'),
  );
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  expect((await investigationRequest).postDataJSON().incident_id).toBe('INC-DEMO-001');
  await streamRequested;
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  release();
  await streamDelivered;
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-002');
  await expect(
    page.getByRole('button', { name: 'View recorded investigation', exact: true }),
  ).toBeEnabled();
  await expect(page.getByTestId('assessment')).not.toBeVisible();
});

test('pending scenario run and reset keep every incident selection control locked', async ({
  page,
}) => {
  await page.goto('/incidents');
  const run = page.getByRole('button', { name: 'Run Incident', exact: true });
  await run.click();
  await expect(run).toBeEnabled();
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await run.click();
  await expect(run).toBeEnabled();
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-002');
  await page.getByLabel('Incident scenario').selectOption('kafka-pricing-lag');
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-001');
  for (const operation of ['run', 'reset']) {
    let release!: () => void;
    let requested!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const pending = new Promise<void>((resolve) => {
      requested = resolve;
    });
    await page.route(
      `**/api/demo/scenarios/kafka-pricing-lag/${operation}`,
      async (route) => {
        requested();
        await gate;
        await route.continue();
      },
      { times: 1 },
    );
    await page
      .getByRole('button', {
        name: operation === 'run' ? 'Run Incident' : 'Reset Scenario',
        exact: true,
      })
      .click();
    await pending;
    try {
      await expect(page.getByLabel('Incident scenario')).toBeDisabled();
      for (const tab of await page.locator('.incident-tabs button').all()) {
        await expect(tab).toBeDisabled();
      }
      await expect(
        page.getByRole('button', { name: 'View recorded investigation', exact: true }),
      ).toBeDisabled();
    } finally {
      release();
    }
    await expect(run).toBeEnabled();
    await expect(page.getByLabel('Incident scenario')).toHaveValue('kafka-pricing-lag');
  }
});

test('a replay citation opens its exact persisted investigation record even before live-window evidence is visible', async ({
  page,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  await expect(page.getByTestId('assessment')).toBeVisible();
  const ids = await page.evaluate(() => ({
    session: localStorage.getItem('creditops-demo-session')!,
    investigation: localStorage.getItem('creditops-investigation:v1:INC-DEMO-001')!,
  }));
  const response = await page.request.get(`/api/investigations/${ids.investigation}`, {
    headers: { 'X-Demo-Session': ids.session },
  });
  const artifact = await response.json();
  const source = artifact.evidence.find(
    (item: { id: string; kind: string; data: { metric?: string } }) =>
      artifact.assessment.supporting_evidence_ids.includes(item.id) &&
      item.kind === 'metric' &&
      item.data.metric === 'quote_age_ms',
  );
  expect(source).toBeTruthy();
  let windowReads = 0;
  await page.route(`**/api/evidence/${source.id}`, (route) => {
    windowReads++;
    return route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Evidence not yet in live clock window' }),
    });
  });
  await page
    .getByTestId('supporting-evidence')
    .getByRole('button', { name: source.id, exact: true })
    .click();
  const drawer = page.getByRole('dialog');
  await expect(drawer.getByText(source.summary, { exact: true })).toBeVisible();
  await expect(drawer).toContainText(source.timestamp);
  await expect(drawer.locator('pre')).toHaveText(JSON.stringify(source.data, null, 2));
  expect(windowReads).toBe(0);
});

test('reload resumes a saved running investigation without starting another investigation', async ({
  page,
}) => {
  await page.goto('/incidents');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  await expect(page.getByTestId('investigation-step').first()).toBeVisible();
  const ids = await page.evaluate(() => ({
    session: localStorage.getItem('creditops-demo-session')!,
    investigation: localStorage.getItem('creditops-investigation:v1:INC-DEMO-001')!,
  }));
  const checkpointResponse = await page.request.get(`/api/investigations/${ids.investigation}`, {
    headers: { 'X-Demo-Session': ids.session },
  });
  const checkpoint = await checkpointResponse.json();
  expect(checkpoint.status).toBe('running');
  await page.route(
    `**/api/investigations/${ids.investigation}`,
    (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(checkpoint),
      }),
    { times: 1 },
  );
  let newRuns = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/investigations')) newRuns++;
  });
  await page.reload();
  await expect(page.getByTestId('failure-domain')).toHaveText(
    /pricing-service.*Kafka consumer backlog/i,
  );
  expect(newRuns).toBe(0);
});
