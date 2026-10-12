import { expect, test, type Page } from './acceptance';

async function runScenario(page: Page, scenario: string, incident: string) {
  await page.goto('/incidents');
  await expect(page.getByLabel('Incident scenario').locator('option')).toHaveCount(3);
  await page.getByLabel('Incident scenario').selectOption(scenario);
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  await expect(page.locator('.incident-banner')).toContainText(incident);
  await expect(page.getByTestId('business-impact')).toBeVisible();
}

for (const [scenario, incident, rfq, state] of [
  ['kafka-pricing-lag', 'INC-DEMO-001', 'RFQ-DEMO-001-001', 'EXPIRED'],
  ['fix-connectivity', 'INC-DEMO-002', 'RFQ-DEMO-002-001', 'UNKNOWN'],
  ['db-pool-exhaustion', 'INC-DEMO-003', 'RFQ-DEMO-003-001', 'TIMED_OUT'],
] as const) {
  test(`${scenario}: event-derived business states, exact citations and responsive timeline`, async ({
    page,
  }) => {
    await runScenario(page, scenario, incident);
    const business = page.getByTestId('business-impact');
    const firstRequest = business.getByTestId('request-journey').filter({ hasText: rfq });
    await expect(
      firstRequest.getByText(state.replaceAll('_', ' '), { exact: true }).first(),
    ).toBeVisible();
    await expect(firstRequest).toContainText('USD 1,000,000.00');
    await expect(firstRequest).toContainText(/\d\.\d+% annual coupon/);
    await expect(firstRequest).toContainText('Execution and settlement are not simulated.');
    if (scenario === 'fix-connectivity') {
      await expect(business.getByTestId('impact-acknowledgements')).toHaveText('0 / 2');
      await expect(firstRequest).toContainText('ORDER-DEMO-002-001');
      await expect(firstRequest).not.toContainText('EXECUTED');
      await expect(firstRequest).not.toContainText('FAILED');
    }
    if (scenario === 'db-pool-exhaustion') {
      await expect(business.getByTestId('impact-processing-timeouts')).toHaveText('2');
      await expect(firstRequest).toContainText('No economic order submitted.');
    }
    const citation = firstRequest.getByRole('button', { name: /^BUSINESS-/ }).first();
    const id = await citation.innerText();
    await citation.click();
    const drawer = page.getByRole('dialog', { name: 'Evidence details' });
    await expect(drawer.getByText(id, { exact: true })).toBeVisible();
    await expect(drawer).toContainText(rfq);
    await expect(drawer).toContainText('rfq-gateway');
    await page.getByRole('button', { name: 'Close evidence' }).click();
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 900 });
      await expect(firstRequest).toBeVisible();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
        `Business lifecycle overflows at ${width}`,
      ).toBe(false);
    }
  });
}

test('switching incidents rejects a late business snapshot from the previous incident', async ({
  page,
}) => {
  await runScenario(page, 'kafka-pricing-lag', 'INC-DEMO-001');
  await page.getByLabel('Incident scenario').selectOption('fix-connectivity');
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Run Incident', exact: true })).toBeEnabled();
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-002');
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let intercepted: () => void = () => {};
  const delayed = new Promise<void>((resolve) => {
    intercepted = resolve;
  });
  let finished: () => void = () => {};
  const delivered = new Promise<void>((resolve) => {
    finished = resolve;
  });
  await page.route('**/api/incidents/INC-DEMO-001/business-impact', async (route) => {
    const response = await route.fetch();
    intercepted();
    await gate;
    await route.fulfill({ response }).catch(() => {});
    finished();
  });
  await page.getByRole('button', { name: 'INC-DEMO-001', exact: false }).click();
  await delayed;
  await page.getByRole('button', { name: 'INC-DEMO-002', exact: false }).click();
  const business = page.getByTestId('business-impact');
  await expect(business).toContainText('RFQ-DEMO-002-001');
  release();
  await delivered;
  await expect(business).toContainText('RFQ-DEMO-002-001');
  await expect(business).not.toContainText('RFQ-DEMO-001-001');
  await expect(page.locator('.incident-banner')).toContainText('INC-DEMO-002');
});

test('adaptive MCP uses a real current snapshot and persists honest transport provenance on reload', async ({
  page,
}) => {
  await runScenario(page, 'kafka-pricing-lag', 'INC-DEMO-001');
  let paidRequests = 0;
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/investigations')) {
      if (request.postDataJSON()?.mode === 'LIVE_AI') paidRequests += 1;
    }
  });
  await page.getByLabel('Investigation path').selectOption('MCP_DEMO');
  const created = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' && response.url().endsWith('/api/investigations'),
  );
  await page.getByRole('button', { name: 'Run adaptive MCP investigation', exact: true }).click();
  const initial = await (await created).json();
  expect(initial.mode).toBe('MCP_DEMO');
  await expect(page.getByTestId('assessment')).toBeVisible();
  const provenance = page.getByTestId('investigation-provenance');
  await expect(provenance).toContainText('Frozen current snapshot');
  await expect(provenance).toContainText('Transport: MCP stdio');
  await expect(provenance).toContainText('Tool schemas verified');
  await expect(page.getByText('MCP · adaptive deterministic', { exact: true })).toBeVisible();
  await expect(page.getByTestId('assessment')).toContainText('uncalibrated support score');
  await expect(page.getByTestId('assessment-qualification')).toContainText('Confirmed cause');
  await expect(page.getByTestId('assessment-qualification')).toContainText('Not established.');
  const session = await page.evaluate(() => localStorage.getItem('creditops-demo-session'));
  const response = await page.request.get(`/api/investigations/${initial.id}`, {
    headers: { 'X-Demo-Session': session! },
  });
  expect(response.ok()).toBe(true);
  const result = await response.json();
  expect(result.provenance.model_called).toBe(false);
  expect(result.provenance.workflow).toBe('evidence_first_v1');
  expect(result.steps.slice(0, 4).map((step: { tool: string }) => step.tool)).toEqual([
    'get_incident',
    'get_service_topology',
    'query_metrics',
    'search_logs',
  ]);
  for (const step of result.steps.slice(0, 4)) {
    expect(step.selected_by).toBe('application_runbook');
    expect(step.provider_turn).toBe(0);
    expect(step.transport).toBe('mcp_stdio');
    expect(step.status).toBe('complete');
  }
  await expect(provenance).toContainText('Workflow: evidence_first_v1');
  await expect(
    page.getByText('Application-runbook initial diagnostic', { exact: true }),
  ).toHaveCount(4);
  await expect(page.getByTestId('assessment-comparison')).toContainText(
    'Validator-authored changes and rejections',
  );
  expect(result.provenance.snapshot_kind).toBe('frozen_current');
  expect(
    result.steps.some(
      (step: { transport: string; status: string }) =>
        step.transport === 'mcp_stdio' && step.status === 'complete',
    ),
  ).toBe(true);
  for (const evidence of result.evidence)
    expect(new Date(evidence.timestamp).valueOf()).toBeLessThanOrEqual(
      new Date(result.provenance.snapshot_cutoff).valueOf(),
    );
  await page.reload();
  await expect(page.getByTestId('assessment')).toBeVisible();
  await expect(page.getByLabel('Investigation path')).toHaveValue('MCP_DEMO');
  await expect(page.getByTestId('investigation-provenance')).toContainText(
    result.provenance.snapshot_cutoff,
  );
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth),
      `Adaptive assessment and provenance overflow at ${width}`,
    ).toBe(false);
  }
  expect(paidRequests).toBe(0);
});
