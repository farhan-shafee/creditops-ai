import { test, expect, type Page } from './acceptance';

type ReadRow = {
  label: string;
  phase: 'active' | 'reset-pending';
  sessionLabel: string;
  aborted: boolean;
  bodyReady: boolean;
};
type Probe = {
  reads: ReadRow[];
  resetPending: boolean;
  holdNext: () => void;
  releaseRead: (label: string, status: number, summary?: string) => void;
  releaseAll: () => void;
  rejectReset: () => void;
};
declare global {
  interface Window {
    resetReadProbe: Probe;
  }
}

// Real Console/API rendering; only response scheduling is controlled. Read labels
// and session equality labels never expose the underlying session capability.
async function observeReads(
  page: Page,
  options: { failReset?: boolean; markCurrent?: boolean } = {},
) {
  await page.addInitScript((options) => {
    const original = window.fetch.bind(window);
    const sessions = new Map<string, string>();
    const held = new Map<string, (status: number, summary?: string) => void>();
    const abandoned = new Map<string, () => void>();
    let failReset = Boolean(options.failReset);
    let rejectReset = () => {};
    let holdNext = false;
    const probe: Probe = {
      reads: [],
      resetPending: false,
      holdNext() {
        holdNext = true;
      },
      releaseRead(label, status, summary) {
        held.get(label)?.(status, summary);
        held.delete(label);
      },
      releaseAll() {
        for (const release of abandoned.values()) release();
        abandoned.clear();
        for (const release of held.values()) release(404);
        held.clear();
      },
      rejectReset() {
        rejectReset();
      },
    };
    window.resetReadProbe = probe;
    window.fetch = async (input, init) => {
      const path = new URL(
        typeof input === 'string' ? input : input instanceof Request ? input.url : input.href,
        location.origin,
      ).pathname;
      const session = new Headers(init?.headers).get('X-Demo-Session') ?? '';
      if (!sessions.has(session)) sessions.set(session, 'session-' + (sessions.size + 1));
      if (path.endsWith('/reset') && init?.method === 'POST') {
        probe.resetPending = true;
        try {
          if (failReset) {
            failReset = false;
            return await new Promise<Response>((_resolve, reject) => {
              rejectReset = () => reject(new Error('Controlled reset failure'));
            });
          }
          return await original(input, init);
        } finally {
          probe.resetPending = false;
        }
      }
      if (!path.endsWith('/business-impact')) return original(input, init);
      const row: ReadRow = {
        label: 'read-' + (probe.reads.length + 1),
        phase: probe.resetPending ? 'reset-pending' : 'active',
        sessionLabel: sessions.get(session)!,
        aborted: Boolean(init?.signal?.aborted),
        bodyReady: false,
      };
      probe.reads.push(row);
      init?.signal?.addEventListener(
        'abort',
        () => {
          row.aborted = true;
        },
        { once: true },
      );
      if (probe.resetPending) {
        // Pause before native dispatch so the pre-fix RED cannot poll a removed
        // resource or need a detector exemption during test containment.
        return await new Promise<Response>((_resolve, reject) => {
          abandoned.set(row.label, () =>
            reject(new DOMException('Controlled obsolete read cancellation', 'AbortError')),
          );
        });
      }
      const firstHeld = holdNext;
      holdNext = false;
      const response = await original(input, firstHeld ? { ...init, signal: undefined } : init);
      if (!response.ok) return response;
      const body = await response.clone().json();
      row.bodyReady = true;
      if (firstHeld)
        return await new Promise<Response>((resolve) => {
          held.set(row.label, (status, summary) =>
            resolve(
              new Response(
                JSON.stringify(
                  status >= 400
                    ? { detail: 'Controlled impact unavailable' }
                    : { ...body, summary },
                ),
                { status, headers: { 'Content-Type': 'application/json' } },
              ),
            ),
          );
        });
      if (!options.markCurrent) return response;
      return new Response(JSON.stringify({ ...body, summary: 'Current generation sample' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };
  }, options);
}
const rows = (page: Page) => page.evaluate(() => window.resetReadProbe.reads);
async function runIncident(page: Page) {
  await page.getByRole('button', { name: 'Run Incident', exact: true }).click();
  await expect(page.getByTestId('incident-detail')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reset Scenario', exact: true })).toBeEnabled();
}
async function openReplay(page: Page) {
  await page.goto('/incidents');
  await runIncident(page);
  await page.getByRole('button', { name: 'View recorded investigation', exact: true }).click();
  await expect(page.getByTestId('assessment')).toBeVisible();
  await expect(page.getByTestId('recorded-business-impact')).toBeVisible();
}
async function holdActiveRead(page: Page) {
  // Development StrictMode can cancel an initial mount read. Hold the already
  // mounted polling loop, identified by a completed sample and its next tick.
  await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
  const before = (await rows(page)).length;
  await page.evaluate(() => window.resetReadProbe.holdNext());
  await page.clock.runFor(2000);
  await expect.poll(async () => (await rows(page)).length).toBe(before + 1);
  await expect.poll(async () => (await rows(page)).at(-1)?.bodyReady).toBe(true);
  const row = (await rows(page)).at(-1)!;
  expect(row.aborted).toBe(false);
  return { label: row.label, count: before + 1 };
}
function barrier() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

// Both the server response and a same-scope read establish actual removal before
// the browser receives reset200; no inference from adjacent log timestamps.
test('ordinary replay reset retains its recorded result and never starts a live impact read', async ({
  page,
  browser,
}, testInfo) => {
  await page.clock.install();
  await observeReads(page);
  await openReplay(page);
  const original = (await page.getByTestId('assessment').textContent())!;
  const before = (await rows(page)).length;
  const hold = barrier();
  let committed = false,
    missingStatus: number | undefined;
  let resetSession = '';
  await page.route('**/api/demo/scenarios/kafka-pricing-lag/reset', async (route) => {
    resetSession = route.request().headers()['x-demo-session'];
    const response = await route.fetch();
    expect(response.status()).toBe(200);
    missingStatus = (
      await page.request.get('/api/incidents/INC-DEMO-001/business-impact', {
        headers: { 'X-Demo-Session': resetSession },
      })
    ).status();
    committed = true;
    await hold.promise;
    await route.fulfill({ response });
  });
  // Keep the displayed input incident stable while the reset response is held.
  // Delay actual overview/incidents responses, rather than inventing their data.
  for (const path of ['overview', 'incidents']) {
    await page.route('**/api/' + path, async (route) => {
      const response = await route.fetch();
      if (committed) await hold.promise;
      await route.fulfill({ response });
    });
  }
  const other = await browser.newContext();
  try {
    const otherPage = await other.newPage();
    await otherPage.goto('/incidents');
    await runIncident(otherPage);
    await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
    await expect.poll(() => committed).toBe(true);
    expect(missingStatus).toBe(404);
    await expect(page.getByRole('button', { name: 'Reset Scenario', exact: true })).toBeDisabled();
    await page.clock.runFor(2000);
    const observed = await rows(page);
    await testInfo.attach('reset-read-ordering', {
      body: JSON.stringify({
        serverAcknowledgedRemoval: committed,
        sameScopeMissingStatus: missingStatus,
        reads: observed,
      }),
      contentType: 'application/json',
    });
    expect(
      observed.length - before,
      'Pending reset may not re-enable live reads after clearing REPLAY',
    ).toBe(0);
    await expect(page.getByTestId('assessment')).toHaveText(original);
    await expect(page.getByTestId('recorded-business-impact')).toBeVisible();
    hold.release();
    await expect(page.getByTestId('incident-detail')).not.toBeVisible();
    const otherSession = await otherPage.evaluate(() =>
      localStorage.getItem('creditops-demo-session'),
    );
    expect(otherSession === resetSession).toBe(false);
    expect(
      (
        await otherPage.request.get('/api/incidents/INC-DEMO-001/business-impact', {
          headers: { 'X-Demo-Session': otherSession! },
        })
      ).status(),
    ).toBe(200);
    await expect(otherPage.getByTestId('incident-detail')).toBeVisible();
  } finally {
    hold.release();
    await expect(page.getByTestId('incident-detail')).not.toBeVisible();
    await page.evaluate(() => window.resetReadProbe.releaseAll());
    await other.close();
  }
});

test('failed ordinary replay reset preserves result and personal scope before a successful reset', async ({
  page,
}) => {
  await page.clock.install();
  await observeReads(page, { failReset: true });
  await openReplay(page);
  const original = (await page.getByTestId('assessment').textContent())!;
  const saved = await page.evaluate(() => {
    const session = localStorage.getItem('creditops-demo-session')!;
    const key =
      'creditops-workspace:v1:' +
      [session, 'INC-DEMO-001', 'test-recording-sha', 'test-export']
        .map(encodeURIComponent)
        .join(':');
    sessionStorage.setItem(key, JSON.stringify({ note: 'Retained personal note', pinnedIds: [] }));
    return { key, investigation: localStorage.getItem('creditops-investigation:v1:INC-DEMO-001') };
  });
  const count = (await rows(page)).length;
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reset Scenario', exact: true })).toBeDisabled();
  await page.clock.runFor(4000);
  expect((await rows(page)).length).toBe(count);
  await expect(page.getByTestId('assessment')).toHaveText(original);
  await page.evaluate(() => window.resetReadProbe.rejectReset());
  await expect(page.getByText('Controlled reset failure', { exact: true })).toBeVisible();
  await expect(page.getByTestId('assessment')).toHaveText(original);
  expect(await page.evaluate((key) => sessionStorage.getItem(key), saved.key)).toContain(
    'Retained personal note',
  );
  expect(
    await page.evaluate(() => localStorage.getItem('creditops-investigation:v1:INC-DEMO-001')),
  ).toBe(saved.investigation);
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByTestId('incident-detail')).not.toBeVisible();
  expect(await page.evaluate((key) => sessionStorage.getItem(key), saved.key)).toBeNull();
  await page.evaluate(() => window.resetReadProbe.releaseAll());
});

for (const status of [200, 404]) {
  test(`reset cancels a pending impact read and rejects late${status} after the same ID reruns`, async ({
    page,
  }) => {
    await page.clock.install();
    await observeReads(page, { markCurrent: true });
    await page.goto('/incidents');
    await runIncident(page);
    const held = await holdActiveRead(page);
    const hold = barrier();
    let committed = false;
    await page.route('**/api/demo/scenarios/kafka-pricing-lag/reset', async (route) => {
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      committed = true;
      await hold.promise;
      await route.fulfill({ response });
    });
    try {
      await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
      await expect.poll(() => committed).toBe(true);
      await expect(
        page.getByRole('button', { name: 'Reset Scenario', exact: true }),
      ).toBeDisabled();
      await page.clock.runFor(4000);
      expect(
        (await rows(page)).find((row) => row.label === held.label)!.aborted,
        'Reset must revoke the pending read before its response returns',
      ).toBe(true);
      expect((await rows(page)).length).toBe(held.count);
      hold.release();
      await expect(page.getByTestId('incident-detail')).not.toBeVisible();
      await runIncident(page);
      await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
      await page.evaluate(
        ({ label, status }) =>
          window.resetReadProbe.releaseRead(label, status, 'Obsolete prior generation sample'),
        { label: held.label, status },
      );
      await page.clock.runFor(1);
      await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
      await expect(page.getByText('Obsolete prior generation sample', { exact: true })).toHaveCount(
        0,
      );
      await expect(page.getByText('Controlled impact unavailable', { exact: false })).toHaveCount(
        0,
      );
    } finally {
      hold.release();
      await page.evaluate(() => window.resetReadProbe.releaseAll());
    }
  });
}

test('failed reset revokes pending live work and restores exactly one polling loop', async ({
  page,
}) => {
  await page.clock.install();
  await observeReads(page, { failReset: true, markCurrent: true });
  await page.goto('/incidents');
  await runIncident(page);
  const held = await holdActiveRead(page);
  await page.getByRole('button', { name: 'Reset Scenario', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Reset Scenario', exact: true })).toBeDisabled();
  await page.clock.runFor(4000);
  expect((await rows(page)).find((row) => row.label === held.label)!.aborted).toBe(true);
  expect((await rows(page)).length).toBe(held.count);
  await page.evaluate(() => window.resetReadProbe.rejectReset());
  await expect(page.getByText('Controlled reset failure', { exact: true })).toBeVisible();
  await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
  await expect.poll(async () => (await rows(page)).length).toBe(held.count + 1);
  await expect.poll(async () => (await rows(page)).at(-1)?.bodyReady).toBe(true);
  await page.evaluate(
    (label) => window.resetReadProbe.releaseRead(label, 200, 'Obsolete prior generation sample'),
    held.label,
  );
  for (let index = 0; index < 3; index += 1) {
    await page.clock.runFor(2000);
    await expect
      .poll(async () => (await rows(page)).filter((row) => row.bodyReady).length)
      .toBe(held.count + index + 2);
  }
  await expect(page.getByText('Obsolete prior generation sample', { exact: true })).toHaveCount(0);
});

test('navigation invalidates a pending live impact response before a later mount', async ({
  page,
}) => {
  await page.clock.install();
  await observeReads(page, { markCurrent: true });
  await page.goto('/incidents');
  await runIncident(page);
  const held = await holdActiveRead(page);
  await page.getByRole('link', { name: 'Incident History', exact: true }).click();
  await expect
    .poll(async () => (await rows(page)).find((row) => row.label === held.label)?.aborted)
    .toBe(true);
  await page.getByRole('link', { name: 'Incidents', exact: true }).click();
  await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
  await page.evaluate(
    (label) => window.resetReadProbe.releaseRead(label, 200, 'Obsolete prior generation sample'),
    held.label,
  );
  await expect(page.getByText('Obsolete prior generation sample', { exact: true })).toHaveCount(0);
});

test('an eligible active impact404 remains visible and can recover on its next poll', async ({
  page,
}) => {
  await page.clock.install();
  await observeReads(page, { markCurrent: true });
  await page.goto('/incidents');
  await runIncident(page);
  const held = await holdActiveRead(page);
  await page.evaluate((label) => window.resetReadProbe.releaseRead(label, 404), held.label);
  await expect(
    page.getByRole('alert').filter({ hasText: 'Controlled impact unavailable' }),
  ).toBeVisible();
  expect((await rows(page)).find((row) => row.label === held.label)!.aborted).toBe(false);
  await page.clock.runFor(2000);
  await expect(page.getByText('Current generation sample', { exact: true })).toBeVisible();
});
