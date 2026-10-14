import { expect, type Page, type Request } from '@playwright/test';

export type RefreshEvent = { phase: string; batch?: number; path?: string; time: number };
type State = { events: RefreshEvent[]; pending: number; active: number };
export async function installRefreshProbe(page: Page, privateCanary: string) {
  await page.clock.install();
  await page.addInitScript(() => {
    const native = window.fetch;
    const events: Array<{ phase: string; batch?: number; path?: string; time: number }> = [];
    const signals = new WeakMap<AbortSignal, number>();
    const groups = new Map<number, { done: boolean; aborted: boolean }>();
    let sequence = 0,
      pending = 0;
    const record = (event: { phase: string; batch?: number; path?: string }) =>
      events.push({ ...event, time: performance.now() });
    window.fetch = async (input, init) => {
      const path = new URL(
        typeof input === 'string' ? input : input instanceof URL ? input.href : input.url,
        location.href,
      ).pathname;
      if (!path.startsWith('/api/')) return native(input, init);
      const signal = init?.signal;
      let batch = signal ? signals.get(signal) : undefined;
      if (path === '/api/overview' && signal && batch === undefined) {
        batch = ++sequence;
        signals.set(signal, batch);
        groups.set(batch, { done: false, aborted: false });
        const id = batch;
        signal.addEventListener(
          'abort',
          () => {
            groups.get(id)!.aborted = true;
            record({ phase: 'refresh_abort', batch: id });
          },
          { once: true },
        );
        record({ phase: 'refresh_start', batch });
      }
      record({ phase: 'fetch_start', path, batch });
      pending++;
      let settled = false;
      const finish = (phase: string) => {
        if (settled) return;
        settled = true;
        pending--;
        record({ phase, path, batch });
        if (path === '/api/metrics/query' && batch !== undefined) groups.get(batch)!.done = true;
      };
      try {
        const response = await native(input, init);
        if (path.endsWith('/events')) finish('stream_headers');
        else {
          const json = response.json.bind(response);
          response.json = async () => {
            try {
              return await json();
            } finally {
              finish('body_done');
            }
          };
        }
        return response;
      } catch (error) {
        finish('fetch_failed');
        throw error;
      }
    };
    const capture = (event: Event) => {
      if ((event.target as Element)?.closest('[data-testid="personal-clear"]'))
        record({ phase: 'clear_capture' });
    };
    const bubble = (event: Event) => {
      if ((event.target as Element)?.closest('[data-testid="personal-clear"]'))
        record({ phase: 'clear_bubble' });
    };
    window.addEventListener('click', capture, true);
    window.addEventListener('click', bubble);
    Object.assign(window, {
      __clearRefreshProbe: {
        record,
        read: () => ({
          events: [...events],
          pending,
          active: [...groups.values()].filter((g) => !g.done && !g.aborted).length,
        }),
        dispose: () => {
          window.fetch = native;
          window.removeEventListener('click', capture, true);
          window.removeEventListener('click', bubble);
        },
      },
    });
  });
  const calls: string[] = [];
  let counting = false;
  let leakedPersonalValues = 0;
  const requested = (request: Request) => {
    const url = new URL(request.url());
    const path = url.pathname;
    if (!path.startsWith('/api/')) return;
    if (
      request.postData()?.includes(privateCanary) ||
      [...url.searchParams.values()].some((value) => value.includes(privateCanary)) ||
      url.pathname.includes(encodeURIComponent(privateCanary))
    )
      leakedPersonalValues++;
    if (counting) calls.push(path);
  };
  page.on('request', requested);
  const state = () =>
    page.evaluate(() =>
      (
        window as typeof window & { __clearRefreshProbe: { read: () => State } }
      ).__clearRefreshProbe.read(),
    );
  const drain = async () => {
    await expect
      .poll(async () => {
        await page.evaluate(() => undefined);
        const s = await state();
        return { pending: s.pending, active: s.active };
      })
      .toEqual({ pending: 0, active: 0 });
  };
  return {
    state,
    drain,
    calls,
    leaks: () => leakedPersonalValues,
    begin: () => {
      calls.length = 0;
      counting = true;
    },
    end: () => {
      counting = false;
    },
    pause: async () => {
      await page.clock.pauseAt('2030-01-02T03:04:05Z');
      await drain();
    },
    dispose: async () => {
      page.off('request', requested);
      await page.evaluate(() =>
        (
          window as typeof window & { __clearRefreshProbe: { dispose: () => void } }
        ).__clearRefreshProbe.dispose(),
      );
    },
  };
}

// The snapshot excludes personal state and captures only recorded presentation.
export async function recordedPresentation(page: Page) {
  return page.getByTestId('recorded-workspace').evaluate((element) => ({
    facts: [...element.querySelectorAll('.recorded-facts')].map((row) => row.textContent),
    overview: element.querySelector('#recorded-panel-0')?.textContent,
    evidence: element.querySelector('#recorded-panel-1')?.textContent,
    review: element.querySelector('#recorded-panel-2')?.textContent,
    samples: [...element.querySelectorAll('[data-testid="timeline-marker"]')].map((row) => ({
      id: row.getAttribute('data-source-id'),
      title: row.querySelector('title')?.textContent,
      x: row.getAttribute('cx') ?? row.getAttribute('x'),
      y: row.getAttribute('cy') ?? row.getAttribute('y'),
    })),
  }));
}

// Preserve the primary assertion as well as any probe disposal failure.
export async function withRefreshProbe(
  page: Page,
  privateCanary: string,
  body: (probe: Awaited<ReturnType<typeof installRefreshProbe>>) => Promise<void>,
) {
  const probe = await installRefreshProbe(page, privateCanary);
  let primary: unknown;
  let failed = false;
  try {
    await body(probe);
  } catch (error) {
    primary = error;
    failed = true;
  }
  try {
    await probe.dispose();
  } catch (cleanup) {
    if (failed)
      throw new AggregateError([primary, cleanup], 'Clear test and probe cleanup failed', {
        cause: primary,
      });
    throw cleanup;
  }
  if (failed) throw primary;
}
