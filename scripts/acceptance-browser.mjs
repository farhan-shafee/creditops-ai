import { isExpectedMockReset } from "./acceptance-detector.mjs";

// Acceptance-only instrumentation. Context response events include every page and popup.
// Route interception records positive proof only when the exact synthetic reset is fulfilled.
export function instrumentAcceptanceBrowser(
  browser,
  { testId, onResponse, onPageError, onConsoleError = () => {} },
) {
  const contexts = new Set(),
    restorations = [],
    listeners = [],
    proof = new WeakMap();
  const pages = new WeakSet();
  const expectedConsole = new Map();
  function patch(object, method, replacement) {
    const original = object[method];
    object[method] = replacement(original.bind(object));
    restorations.push(() => {
      object[method] = original;
    });
  }
  function wrapHandler(handler) {
    return async (route, request) => {
      const fulfill = route.fulfill.bind(route);
      route.fulfill = async (options) => {
        const metadata = {
          status: options.status ?? 200,
          method: request.method(),
          url: request.url(),
          testId,
          mockedResetProof: { fulfilled: true, detail: options.json?.detail },
        };
        if (isExpectedMockReset(metadata)) {
          proof.set(request, metadata.mockedResetProof);
          expectedConsole.set(request.url(), metadata);
        }
        try {
          return await fulfill(options);
        } catch (error) {
          proof.delete(request);
          expectedConsole.delete(request.url());
          throw error;
        }
      };
      return handler(route, request);
    };
  }
  function observePage(page) {
    if (pages.has(page)) return;
    pages.add(page);
    const error = () => onPageError({ testId });
    page.on("pageerror", error);
    const consoleMessage = (message) => {
      if (message.type() !== "error") return;
      const url = message.location().url;
      onConsoleError({
        testId,
        url,
        text: message.text(),
        mockedResponse: expectedConsole.get(url),
      });
    };
    page.on("console", consoleMessage);
    listeners.push(() => {
      page.off("pageerror", error);
      page.off("console", consoleMessage);
    });
    patch(
      page,
      "route",
      (original) => (url, handler, options) =>
        original(url, wrapHandler(handler), options),
    );
  }
  function observeContext(context) {
    if (contexts.has(context)) return;
    contexts.add(context);
    const response = (value) => {
      const metadata = {
        status: value.status(),
        url: value.url(),
        method: value.request().method(),
        testId,
        mockedResetProof: proof.get(value.request()),
      };
      if (!isExpectedMockReset(metadata)) expectedConsole.delete(value.url());
      onResponse(metadata);
    };
    context.on("response", response);
    context.on("page", observePage);
    listeners.push(() => {
      context.off("response", response);
      context.off("page", observePage);
    });
    context.pages().forEach(observePage);
    patch(
      context,
      "route",
      (original) => (url, handler, options) =>
        original(url, wrapHandler(handler), options),
    );
  }
  browser.contexts().forEach(observeContext);
  patch(browser, "newContext", (original) => async (...args) => {
    const context = await original(...args);
    observeContext(context);
    return context;
  });
  patch(browser, "newPage", (original) => async (...args) => {
    const page = await original(...args);
    observeContext(page.context());
    observePage(page);
    return page;
  });
  return {
    contexts,
    detach() {
      listeners.forEach((remove) => remove());
      restorations.reverse().forEach((restore) => restore());
    },
  };
}
