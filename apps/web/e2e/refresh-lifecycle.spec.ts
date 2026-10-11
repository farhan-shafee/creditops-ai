import { test, expect } from '@playwright/test';

const overview = {
  services: [],
  active_incidents: [],
  kafka: { status: 'healthy', consumer_lag: 3, topic_count: 6 },
  fix: { status: 'healthy', connected: true, session_count: 2, reconnect_count: 0 },
  database: { status: 'healthy', pool_utilization: 0.35, query_latency_ms: 12 },
  investigation_count: 0,
  clock: { label: 'Synthetic clock', scale: 12 },
  telemetry_mode: 'persisted',
};

// These tests mount the real Console and defer only its HTTP dependency.
// Timers advance through Playwright's clock; no wall-clock sleep or backend is needed.
test('console refresh owns one pending batch across timer ticks and settles after release', async ({
  page,
}) => {
  await page.clock.install();
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const requests: Record<string, number> = {};
  let holding = true;
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    requests[pathname] = (requests[pathname] ?? 0) + 1;
    if (holding && ['/api/overview', '/api/incidents', '/api/services/topology'].includes(pathname))
      await gate;
    const value =
      pathname === '/api/overview'
        ? overview
        : pathname === '/api/services/topology'
          ? { services: [], dependencies: [] }
          : pathname === '/api/evaluations/latest'
            ? { results: [], selected_recordings: [], summary: {} }
            : [];
    await route.fulfill({ status: 200, json: value });
  });
  try {
    await page.goto('/');
    await expect.poll(() => requests['/api/overview']).toBe(1);
    await page.clock.runFor(6000);
    expect(requests['/api/overview']).toBe(1);
    expect(requests['/api/incidents']).toBe(1);
    expect(requests['/api/services/topology']).toBe(1);
    holding = false;
    release();
    await expect(page.getByText('API connected', { exact: true })).toBeVisible();
    await page.clock.runFor(2000);
    await expect.poll(() => requests['/api/overview']).toBe(2);
  } finally {
    release();
  }
});

test('console unmount aborts its pending refresh and later mount succeeds', async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.fetch;
    const counts = { signalled: 0, aborted: 0 };
    Object.assign(window, { refreshLifecycleCounts: counts });
    window.fetch = (input, init) => {
      if (
        typeof input === 'string' &&
        ['/api/overview', '/api/incidents', '/api/services/topology'].includes(input)
      ) {
        if (init?.signal) {
          counts.signalled += 1;
          init.signal.addEventListener(
            'abort',
            () => {
              counts.aborted += 1;
            },
            { once: true },
          );
        }
      }
      return original(input, init);
    };
  });
  let pending = 0;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route('**/api/**', async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (['/api/overview', '/api/incidents', '/api/services/topology'].includes(pathname)) {
      pending += 1;
      if (pending <= 3) await gate;
    }
    await route.fulfill({
      status: 200,
      json:
        pathname === '/api/overview'
          ? overview
          : pathname === '/api/services/topology'
            ? { services: [], dependencies: [] }
            : pathname === '/api/evaluations/latest'
              ? { results: [], selected_recordings: [], summary: {} }
              : [],
    });
  });
  try {
    await page.goto('/');
    await expect.poll(() => pending).toBe(3);
    // A client navigation unmounts the Console without discarding the browser document.
    await page.getByRole('link', { name: 'Incidents', exact: true }).click();
    await expect
      .poll(
        () =>
          page.evaluate(
            () =>
              (
                window as typeof window & {
                  refreshLifecycleCounts: { aborted: number };
                }
              ).refreshLifecycleCounts.aborted,
          ),
        { timeout: 3000 },
      )
      .toBe(3);
    release();
    await expect(page.getByText('API connected', { exact: true })).toBeVisible();
  } finally {
    release();
  }
});

test('console discards a held pre-run refresh when the incident identity stays the same', async ({
  page,
}) => {
  await page.clock.install();
  const oldIncident = {
    id: 'INC-DEMO-001',
    scenario: 'kafka-pricing-lag',
    title: 'Old snapshot',
    severity: 'SEV2',
    status: 'detected',
    started_at: '2026-10-09T14:00:00Z',
    affected_services: [],
    client_impact: 'Synthetic impact',
    summary: 'Original snapshot',
    timeline: [],
    simulated_elapsed_seconds: 0,
  };
  const created = {
    ...oldIncident,
    title: 'New snapshot',
    status: 'monitoring',
    simulated_elapsed_seconds: 24,
  };
  let current = oldIncident;
  let holding = false,
    held = 0,
    settled = 0,
    ran = false;
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  const metricsScopes: string[] = [];
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/run') && route.request().method() === 'POST') {
      ran = true;
      current = created;
      return route.fulfill({ status: 200, json: created });
    }
    const snapshot = current;
    const deferred =
      holding &&
      held < 3 &&
      ['/api/overview', '/api/incidents', '/api/services/topology'].includes(url.pathname);
    if (deferred) {
      held += 1;
      await gate;
    }
    const value =
      url.pathname === '/api/overview'
        ? { ...overview, active_incidents: [snapshot] }
        : url.pathname === '/api/incidents'
          ? [snapshot]
          : url.pathname === '/api/services/topology'
            ? { services: [], dependencies: [] }
            : url.pathname === '/api/scenarios'
              ? [
                  {
                    id: 'kafka-pricing-lag',
                    title: 'Kafka scenario',
                    incident_id: 'INC-DEMO-001',
                    description: 'Synthetic scenario',
                  },
                ]
              : url.pathname === '/api/evaluations/latest'
                ? { selected_recordings: [] }
                : url.pathname.endsWith('/business-impact')
                  ? null
                  : [];
    if (url.pathname === '/api/metrics/query' && ran)
      metricsScopes.push(url.searchParams.get('incident_id') ?? '');
    try {
      await route.fulfill({ status: 200, json: value });
    } finally {
      if (deferred) settled += 1;
    }
  });
  try {
    await page.goto('/incidents');
    await expect(page.getByText('API connected', { exact: true })).toBeVisible();
    await expect(page.getByText('Old snapshot', { exact: true }).first()).toBeVisible();
    await page.clock.pauseAt(new Date(Date.now() + 100));
    holding = true;
    await page.clock.runFor(2000);
    await expect.poll(() => held).toBe(3);
    await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
    await expect.poll(() => ran).toBe(true);
    await expect(page.getByText('New snapshot', { exact: true }).first()).toBeVisible();
    holding = false;
    release();
    await expect.poll(() => settled).toBe(3);
    await page.clock.runFor(1);
    await expect(page.getByText('New snapshot', { exact: true }).first()).toBeVisible({
      timeout: 3000,
    });
    await expect(page.getByText('Old snapshot', { exact: true })).toHaveCount(0);
    await expect.poll(() => metricsScopes.length).toBeGreaterThan(0);
    expect(metricsScopes.every((id) => id === 'INC-DEMO-001')).toBe(true);
  } finally {
    holding = false;
    release();
  }
});
