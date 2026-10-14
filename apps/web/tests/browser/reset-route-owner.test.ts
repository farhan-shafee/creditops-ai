import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { test } from 'node:test';
import { chromium, type Page } from '@playwright/test';
import { instrumentAcceptanceBrowser } from '../../../../scripts/acceptance-browser.mjs';
import { withResetRouteOwner } from '../../e2e/reset-route-owner';

function barrier() {
  let release!: () => void;
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

for (const primaryFailure of [false, true]) {
  test(
    `reset route ownership joins native forwarding before disposal (${primaryFailure ? 'assertion failure' : 'success'})`,
    { timeout: 20_000 },
    async () => {
      const arrived = barrier(),
        release = barrier(),
        finished = barrier();
      const events: string[] = [];
      const server = createServer(async (request, response) => {
        if (request.url === '/owned') {
          events.push('native-request-arrived');
          arrived.release();
          await release.promise;
          response.end('real local server response');
        } else response.end('<!doctype html><title>Isolated route ownership</title>');
      });
      server.listen(0, '127.0.0.1');
      await once(server, 'listening');
      const address = server.address() as { port: number };
      const browser = await chromium.launch();
      const context = await browser.newContext(),
        other = await browser.newContext();
      const page: Page = await context.newPage();
      const detectorEvents: number[] = [];
      const instrumentation = instrumentAcceptanceBrowser(browser, {
        testId: 'controlled reset ownership',
        onResponse: (response: { status: number }) => {
          detectorEvents.push(response.status);
        },
        onPageError: () => {
          throw new Error('Unexpected controlled page error');
        },
      });
      const primary = new Error('Intentional primary reset assertion');
      let scope: Promise<void> | undefined,
        forwardingStarted = false;
      try {
        await page.goto(`http://127.0.0.1:${address.port}/`);
        let unrelatedCalls = 0;
        if (primaryFailure)
          await page.route('**/owned', async (route) => {
            unrelatedCalls += 1;
            await route.fallback();
          });
        scope = withResetRouteOwner(
          page,
          {
            releaseBarrier: () => {
              events.push('barrier-release');
              release.release();
            },
            releaseProbe: async () => {
              events.push('probe-release');
            },
            closeOther: async () => {
              events.push('context-disposal-entry');
              try {
                assert.ok(
                  events.includes('fulfill-complete'),
                  'Context disposal must follow owned forwarding completion',
                );
              } finally {
                await other.close();
                events.push('secondary-context-closed');
              }
            },
          },
          async (owner) => {
            await owner.route('/owned', async (route) => {
              forwardingStarted = true;
              events.push('fetch-start');
              try {
                const response = await route.fetch();
                events.push('fetch-complete');
                assert.equal(response.status(), 200);
                await route.fulfill({ response });
                events.push('fulfill-complete');
              } finally {
                finished.release();
              }
            });
            await page.evaluate(() => {
              void fetch('/owned').then(
                () => undefined,
                () => undefined,
              );
            });
            await arrived.promise;
            events.push('test-body-outcome');
            if (primaryFailure) throw primary;
          },
        );
        if (primaryFailure) await assert.rejects(scope, (error) => error === primary);
        else await scope;
        await finished.promise;
        assert.ok(events.indexOf('barrier-release') < events.indexOf('fetch-complete'));
        assert.ok(events.indexOf('fulfill-complete') < events.indexOf('context-disposal-entry'));
        assert.ok(
          detectorEvents.length > 0,
          'Acceptance listeners stay active during ownership cleanup',
        );
        // Registration was removed; a later same-path request bypasses this owner.
        const before = events.filter((event) => event === 'fetch-start').length;
        await page.evaluate(() => fetch('/owned').then((response) => response.text()));
        assert.equal(events.filter((event) => event === 'fetch-start').length, before);
        assert.equal(
          unrelatedCalls,
          primaryFailure ? 1 : 0,
          'Scoped removal preserves other handler registrations',
        );
        console.log(JSON.stringify({ primaryFailure, events, primaryPreserved: primaryFailure }));
      } finally {
        release.release();
        if (scope) await scope.catch(() => undefined); // Already asserted/observed above; containment only.
        if (forwardingStarted) await finished.promise;
        await other.close();
        await context.close();
        instrumentation.detach();
        await browser.close();
        server.close();
        await once(server, 'close');
      }
    },
  );
}

test(
  'reset ownership reports primary and cleanup failures while still closing resources',
  { timeout: 20_000 },
  async () => {
    const browser = await chromium.launch();
    const context = await browser.newContext(),
      other = await browser.newContext();
    const page = await context.newPage();
    const primary = new Error('Intentional primary assertion'),
      cleanup = new Error('Intentional probe cleanup error');
    const events: string[] = [];
    try {
      await assert.rejects(
        withResetRouteOwner(
          page,
          {
            releaseBarrier: () => {
              events.push('barrier-release');
            },
            releaseProbe: async () => {
              events.push('probe-release');
              throw cleanup;
            },
            closeOther: async () => {
              await other.close();
              events.push('secondary-context-closed');
            },
          },
          async () => {
            throw primary;
          },
        ),
        (error) => {
          assert.ok(error instanceof AggregateError);
          assert.equal(error.cause, primary);
          assert.deepEqual(error.errors, [primary, cleanup]);
          return true;
        },
      );
      assert.deepEqual(events, ['barrier-release', 'probe-release', 'secondary-context-closed']);
      console.log(
        JSON.stringify({
          observedPrimary: primary.message,
          observedCleanup: cleanup.message,
          events,
        }),
      );
    } finally {
      await other.close();
      await context.close();
      await browser.close();
    }
  },
);
test(
  'reset admission closes before cleanup yields while unrelated routing remains available',
  { timeout: 20_000 },
  async () => {
    const arrived = barrier(),
      release = barrier();
    let nativeRequests = 0,
      forwardCalls = 0,
      unrelatedCalls = 0;
    const server = createServer(async (request, response) => {
      if (request.url === '/owned' && ++nativeRequests === 1) {
        arrived.release();
        await release.promise;
      }
      response.end(
        request.url === '/'
          ? '<!doctype html><title>Admission</title>'
          : 'actual loopback response',
      );
    });
    server.listen(0, '127.0.0.1');
    await once(server, 'listening');
    const address = server.address() as { port: number };
    const browser = await chromium.launch(),
      context = await browser.newContext();
    const page = await context.newPage();
    let scope: Promise<void> | undefined;
    try {
      await page.goto(`http://127.0.0.1:${address.port}/`);
      await page.route('**/owned', async (route) => {
        unrelatedCalls++;
        await route.fallback();
      });
      scope = withResetRouteOwner(
        page,
        {
          releaseBarrier: () => {},
          releaseProbe: async () => {
            try {
              await page.evaluate(() => fetch('/owned').then((response) => response.text()));
              assert.equal(
                forwardCalls,
                1,
                'A request entering during cleanup must not start controlled forwarding',
              );
              assert.equal(unrelatedCalls, 1);
            } finally {
              release.release();
            }
          },
          closeOther: async () => {
            assert.equal(forwardCalls, 1);
          },
        },
        async (owner) => {
          await owner.route('/owned', async (route) => {
            forwardCalls++;
            const response = await route.fetch();
            await route.fulfill({ response });
          });
          await page.evaluate(() => {
            void fetch('/owned').then(
              () => undefined,
              () => undefined,
            );
          });
          await arrived.promise;
        },
      );
      await scope;
      await page.evaluate(() => fetch('/owned').then((response) => response.text()));
      assert.equal(forwardCalls, 1);
      assert.equal(unrelatedCalls, 2, 'The exact unrelated matcher survives scoped removal');
      console.log(
        JSON.stringify({
          phase: 'request-during-drain',
          forwardCalls,
          unrelatedCalls,
          nativeRequests,
        }),
      );
    } finally {
      release.release();
      if (scope) await scope.catch(() => undefined);
      await context.close();
      await browser.close();
      server.close();
      await once(server, 'close');
    }
  },
);
