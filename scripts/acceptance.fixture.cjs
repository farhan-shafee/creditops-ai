const { createRequire } = require("node:module");
const { join, resolve } = require("node:path");
const { existsSync, readFileSync, writeFileSync } = require("node:fs");
const { createAcceptanceDetector } = require("./acceptance-detector.mjs");
const { instrumentAcceptanceBrowser } = require("./acceptance-browser.mjs");
const root = resolve(__dirname, "..");
const requireWeb = createRequire(join(root, "apps/web/package.json"));
const { test: base, expect } = requireWeb("@playwright/test");
exports.expect = expect;
exports.test = base.extend({
  _acceptanceOwnership: [
    async ({ browser, context }, use, testInfo) => {
      const directory = process.env.ACCEPTANCE_RESULT_DIR;
      if (!directory)
        throw new Error(
          "Instrumented acceptance requires a unique ACCEPTANCE_RESULT_DIR",
        );
      const failurePath = join(directory, "acceptance-failure.json");
      if (existsSync(failurePath))
        throw new Error(
          "Acceptance previously latched a failure; no new test may start",
        );
      const detector = createAcceptanceDetector({
        onFailure: (row) => {
          if (!existsSync(failurePath))
            writeFileSync(failurePath, JSON.stringify(row, null, 2), {
              flag: "wx",
            });
          console.log("ACCEPTANCE_FAILURE " + JSON.stringify(row));
        },
      });
      const instrumentation = instrumentAcceptanceBrowser(browser, {
        testId: testInfo.title,
        onResponse: (response) => detector.observeResponse(response),
        onPageError: (error) => detector.observePageError(error),
        onConsoleError: (error) => detector.observeConsoleError(error),
      });
      // The normal context is created before the auto fixture and is also observed.
      if (!instrumentation.contexts.has(context))
        throw new Error("Normal browser context was not instrumented");
      try {
        await use();
      } finally {
        instrumentation.detach();
        const state = detector.snapshot();
        await testInfo.attach("acceptance-detector", {
          body: JSON.stringify(state, null, 2),
          contentType: "application/json",
        });
      }
      if (existsSync(failurePath)) {
        const failure = JSON.parse(readFileSync(failurePath, "utf8"));
        throw new Error("Acceptance latched failure: " + failure.kind);
      }
    },
    { auto: true },
  ],
});
