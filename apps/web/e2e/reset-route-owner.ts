import type { Page, Route } from '@playwright/test';

type Cleanup = {
  releaseBarrier: () => void;
  releaseProbe: () => Promise<void>;
  closeOther: () => Promise<void>;
};
type Owner = { route: (path: string, forward: (route: Route) => Promise<void>) => Promise<void> };

// This test owns only its unique matchers, not other routes or detector listeners.
export async function withResetRouteOwner(
  page: Page,
  cleanup: Cleanup,
  body: (owner: Owner) => Promise<void>,
) {
  const matches: ((url: URL) => boolean)[] = [];
  const active = new Set<Promise<void>>();
  const failures: unknown[] = [];
  let stopping = false;
  const owner: Owner = {
    async route(path, forward) {
      if (stopping) throw new Error('Reset interception owner is closed');
      const matcher = (url: URL) => url.pathname === path;
      matches.push(matcher);
      await page.route(matcher, (route) => {
        const admitted = !stopping;
        const work = Promise.resolve().then(() => (admitted ? forward(route) : route.fallback()));
        active.add(work);
        // Observe settled failures separately: leaving active must not lose them.
        void work.then(
          () => {
            active.delete(work);
          },
          (error) => {
            active.delete(work);
            failures.push(error);
          },
        );
        return work;
      });
    },
  };
  let primary: unknown,
    bodyFailed = false;
  try {
    await body(owner);
  } catch (error) {
    primary = error;
    bodyFailed = true;
  }
  const attempt = async (action: () => void | Promise<void>) => {
    try {
      await action();
    } catch (error) {
      failures.push(error);
    }
  };
  // Unblock every dependency before joining; assertions never guard cleanup.
  stopping = true;
  await attempt(cleanup.releaseBarrier);
  await attempt(cleanup.releaseProbe);
  // Stop new controlled forwarding synchronously, then drain admitted work.
  // Removing the last SDK interception pattern early can continue an active route.
  while (active.size) await Promise.allSettled([...active]);
  // No await separates the final empty check from scoped SDK unregistration.
  // Unique matcher identity survives the acceptance fixture's handler wrapper.
  const removals = await Promise.allSettled(matches.map((matcher) => page.unroute(matcher)));
  for (const removal of removals) if (removal.status === 'rejected') failures.push(removal.reason);
  await attempt(cleanup.closeOther);
  if (bodyFailed && failures.length)
    throw new AggregateError([primary, ...failures], 'Reset test and cleanup failed', {
      cause: primary,
    });
  if (bodyFailed) throw primary;
  if (failures.length) throw new AggregateError(failures, 'Reset test cleanup failed');
}
