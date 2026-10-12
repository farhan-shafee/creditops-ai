import assert from "node:assert/strict";
import { test } from "node:test";
import { createAcceptanceDetector } from "./acceptance-detector.mjs";

const mockedTitle =
  "workspace notes: failed reset preserves notes and successful reset clears captured incident";

test("real browser 500 latches failure even if a later UI result passes", () => {
  const failures = [];
  const detector = createAcceptanceDetector({
    onFailure: (row) => failures.push(row),
    now: () => "2026-10-11T21:00:00.000Z",
  });
  detector.observeResponse({
    status: 500,
    url: "http://127.0.0.1:3100/api/incidents",
    method: "GET",
    testId: "passing UI assertion",
  });
  detector.feedLog(
    "backend",
    'INFO: 127.0.0.1:1 - "GET /api/overview HTTP/1.1" 200 OK\n',
  );
  assert.equal(failures.length, 1);
  assert.equal(detector.snapshot().failure.kind, "browser-http-5xx");
  assert.equal(
    detector.snapshot().failure.detectedAt,
    "2026-10-11T21:00:00.000Z",
  );
});

test("split backend access and QueuePool error output cannot escape detection", () => {
  for (const chunks of [
    [
      'INFO: 127.0.0.1:7 - "GET /api/overview HTTP/1.1" 5',
      "00 Internal Server Error\n",
    ],
    [
      "sqlalchemy.exc.TimeoutError: Queue",
      "Pool limit of size 5 overflow 10 reached, connection timed out, timeout 30.00\n",
    ],
    ["ERROR: Exception in ASGI appli", "cation\n"],
  ]) {
    const detector = createAcceptanceDetector();
    chunks.forEach((chunk) => detector.feedLog("backend", chunk));
    assert.ok(detector.snapshot().failure);
  }
});

test("a backend reset500 is always real even in the intentional mocked-reset case", () => {
  const detector = createAcceptanceDetector();
  detector.feedLog(
    "backend",
    'INFO: 127.0.0.1:1 - "POST /api/demo/scenarios/kafka-pricing-lag/reset HTTP/1.1" 500 Internal Server Error\n',
  );
  assert.equal(detector.snapshot().failure.kind, "backend-http-5xx");
});

test("only exact test, route, method, status and positive fulfill proof excuse mocked reset500", () => {
  const response = {
    status: 500,
    url: "http://127.0.0.1:3100/api/demo/scenarios/kafka-pricing-lag/reset",
    method: "POST",
    testId: mockedTitle,
    mockedResetProof: { fulfilled: true, detail: "Reset failed" },
  };
  const good = createAcceptanceDetector();
  good.observeResponse(response);
  assert.equal(good.snapshot().failure, null);
  assert.equal(good.snapshot().expectedMockResponses, 1);
  for (const changed of [
    { testId: "other test" },
    { method: "GET" },
    { status: 503 },
    { url: "http://127.0.0.1:3100/api/demo/scenarios/fix-connectivity/reset" },
    { mockedResetProof: undefined },
    { mockedResetProof: { fulfilled: true, detail: "Other failure" } },
  ]) {
    const detector = createAcceptanceDetector();
    detector.observeResponse({ ...response, ...changed });
    assert.ok(detector.snapshot().failure);
  }
});

test("production frontend5xx, errors and browser pageerrors latch while ordinary logs do not", () => {
  for (const [source, line] of [
    ["frontend", " GET /incidents 500 in 7ms\n"],
    ["frontend", "Error: missing server manifest\n"],
    ["frontend", "UnhandledPromiseRejection: broken\n"],
  ]) {
    const detector = createAcceptanceDetector();
    detector.feedLog(source, line);
    assert.ok(detector.snapshot().failure);
  }
  const detector = createAcceptanceDetector();
  detector.feedLog("frontend", "Ready in 1s\n GET / 200 in 3ms\n");
  detector.feedLog("backend", '{"event":"http_request","status":403}\n');
  assert.equal(detector.snapshot().failure, null);
  detector.observePageError({
    testId: "any page",
    message: "Uncaught runtime failure",
  });
  assert.equal(detector.snapshot().failure.kind, "browser-page-error");
});

test("failure, stop-start and owned-cleanup completion have separate immutable timestamps", () => {
  let time = "first";
  const detector = createAcceptanceDetector({ now: () => time });
  detector.feedLog(
    "backend",
    "QueuePool limit of size 5 overflow 10 reached\n",
  );
  time = "stop";
  detector.markStopStarted();
  time = "cleanup";
  detector.markStopped();
  time = "later";
  detector.observeResponse({
    status: 503,
    url: "http://127.0.0.1/api/overview",
    method: "GET",
  });
  const receipt = detector.snapshot();
  assert.equal(receipt.failure.detectedAt, "first");
  assert.equal(receipt.stopStartedAt, "stop");
  assert.equal(receipt.stoppedAt, "cleanup");
  assert.equal(receipt.failure.kind, "backend-pool-timeout");
});
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { resolve, join, relative } from "node:path";
import { instrumentAcceptanceBrowser } from "./acceptance-browser.mjs";

const root = resolve(import.meta.dirname, "..");
const requireWeb = createRequire(join(root, "apps/web/package.json"));
const { chromium } = requireWeb("@playwright/test");

test("live loopback responses from preexisting, explicit and convenience contexts are all observed", async () => {
  const server = createServer((request, response) => {
    response.writeHead(request.url === "/bad" ? 500 : 200, {
      "content-type": "text/html",
    });
    response.end(
      "<!doctype html><title>Visible passing UI</title><p>Visible passing UI</p>",
    );
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  let instrumentation;
  try {
    const existing = await browser.newContext();
    const first = await existing.newPage();
    const responses = [];
    instrumentation = instrumentAcceptanceBrowser(browser, {
      testId: "any test",
      onResponse: (row) => responses.push(row),
      onPageError() {},
    });
    const explicit = await browser.newContext();
    const second = await explicit.newPage();
    const convenience = await browser.newPage();
    const extra = await explicit.newPage();
    for (const page of [first, second, convenience, extra]) {
      await page.goto(url + "/bad");
      assert.equal(await page.title(), "Visible passing UI");
    }
    assert.equal(responses.filter((row) => row.status === 500).length, 4);
    assert.equal(instrumentation.contexts.size, 3);
  } finally {
    instrumentation?.detach();
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("live fulfilled reset500 has positive exact proof while a later real same-route500 fails", async () => {
  const server = createServer((request, response) => {
    response.writeHead(request.method === "POST" ? 500 : 200, {
      "content-type": "text/html",
    });
    response.end("<!doctype html><title>Offline fixture</title>");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  let instrumentation;
  try {
    const detector = createAcceptanceDetector();
    instrumentation = instrumentAcceptanceBrowser(browser, {
      testId: mockedTitle,
      onResponse: (row) => detector.observeResponse(row),
      onPageError: (row) => detector.observePageError(row),
    });
    const page = await browser.newPage();
    const route = "**/api/demo/scenarios/kafka-pricing-lag/reset";
    await page.route(route, (value) =>
      value.fulfill({ status: 500, json: { detail: "Reset failed" } }),
    );
    await page.goto(url);
    await page.evaluate(() =>
      fetch("/api/demo/scenarios/kafka-pricing-lag/reset", {
        method: "POST",
      }).then((response) => response.text()),
    );
    assert.equal(detector.snapshot().failure, null);
    assert.equal(detector.snapshot().expectedMockResponses, 1);
    await page.unroute(route);
    await page.evaluate(() =>
      fetch("/api/demo/scenarios/kafka-pricing-lag/reset", {
        method: "POST",
      }).then((response) => response.text()),
    );
    assert.equal(detector.snapshot().failure.kind, "browser-http-5xx");
  } finally {
    instrumentation?.detach();
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { pathToFileURL } from "node:url";

// The pinned runner, real browser fixture and IPC bridge must stop scheduling
// after a passing-looking page receives a real server error.
test(
  "first real browser error interrupts Playwright through SIGINT before a later case starts",
  { timeout: 12000 },
  async () => {
    const proof = join(
      root,
      "artifacts/test-tmp/acceptance-stop-" + process.pid + "-" + Date.now(),
    );
    mkdirSync(join(proof, "cases"), { recursive: true });
    const server = createServer((_, response) => {
      response.writeHead(500, { "content-type": "text/html" });
      response.end("<!doctype html><title>Passing UI</title><p>Passing UI</p>");
    });
    await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
    const url = `http://127.0.0.1:${server.address().port}`;
    const fixture = relative(
      join(proof, "cases"),
      join(root, "scripts/acceptance.fixture.cjs"),
    ).replaceAll("\\", "/");
    writeFileSync(
      join(proof, "cases/proof.spec.ts"),
      `import { test, expect } from ${JSON.stringify(fixture)};
    test('passing-looking first case', async ({ page }) => {
      console.log('STARTED_FIRST');
      await page.goto(${JSON.stringify(url)});
      await expect(page.getByText('Passing UI', { exact: true })).toBeVisible();
      await page.getByRole('button', {name: 'Never exists'}).click();
    });
    test('later case must never start', async () => { console.log('STARTED_LATER'); });
  `,
    );
    writeFileSync(
      join(proof, "config.mjs"),
      `export default { testDir: './cases', fullyParallel: false, workers: 1, retries: 0, maxFailures: 1, timeout: 10000, outputDir: './results', reporter: [['list'], ['json', {outputFile: './report.json'}]], use: { headless: true } };`,
    );
    const requireTest = createRequire(requireWeb.resolve("@playwright/test"));
    const playwright = createRequire(
      requireTest.resolve("playwright/package.json"),
    );
    const cli = join(
      resolve(playwright.resolve("playwright/package.json"), ".."),
      "cli.js",
    );
    const bridge = pathToFileURL(
      join(root, "scripts/acceptance-stop.mjs"),
    ).href;
    const child = spawn(
      process.execPath,
      [
        "--import",
        bridge,
        cli,
        "test",
        "--config=" + join(proof, "config.mjs"),
      ],
      {
        cwd: proof,
        env: {
          ...process.env,
          ACCEPTANCE_RESULT_DIR: proof,
          CREDITOPS_ENV_FILE: "",
          OPENAI_API_KEY: "",
          ANTHROPIC_API_KEY: "",
          ADMIN_API_KEY: "",
        },
        stdio: ["ignore", "pipe", "pipe", "ipc"],
        windowsHide: true,
      },
    );
    let output = "",
      sent = false,
      timer;
    const detector = createAcceptanceDetector({
      onFailure: () => {
        detector.markStopStarted();
        sent = true;
        child.send({ type: "acceptance-stop" });
      },
    });
    const receive = (chunk) => {
      output += chunk.toString();
      for (const line of output.split("\n")) {
        const start = line.indexOf("ACCEPTANCE_FAILURE ");
        if (start >= 0 && !sent) {
          try {
            detector.observeFailure(
              JSON.parse(line.slice(start + "ACCEPTANCE_FAILURE ".length)),
            );
          } catch (error) {
            if (!(error instanceof SyntaxError)) throw error;
          }
        }
      }
    };
    child.stdout.on("data", receive);
    child.stderr.on("data", receive);
    try {
      const exit = await Promise.race([
        new Promise((resolve, reject) => {
          child.once("error", reject);
          child.once("exit", (code) => resolve(code));
        }),
        new Promise((_, reject) => {
          timer = setTimeout(
            () =>
              reject(
                new Error(
                  "Owned Playwright runner failed to stop within 9 seconds",
                ),
              ),
            9000,
          );
        }),
      ]);
      writeFileSync(join(proof, "runner.log"), output);
      detector.markStopped();
      assert.ok(exit !== 0);
      assert.ok(sent, output);
      assert.match(output, /ACCEPTANCE_STOP_ACK/);
      assert.match(output, /STARTED_FIRST/);
      assert.doesNotMatch(output, /^STARTED_LATER$/m);
      assert.ok(existsSync(join(proof, "acceptance-failure.json")));
      const receipt = detector.snapshot();
      assert.equal(receipt.failure.kind, "browser-http-5xx");
      assert.ok(
        Date.parse(receipt.stoppedAt) - Date.parse(receipt.failure.detectedAt) <
          5000,
      );
      writeFileSync(
        join(proof, "stop-receipt.json"),
        JSON.stringify(receipt, null, 2),
      );
      assert.equal(
        JSON.parse(readFileSync(join(proof, "acceptance-failure.json"))).status,
        500,
      );
    } finally {
      clearTimeout(timer);
      if (child.exitCode === null) {
        const closed = new Promise((resolve) => child.once("close", resolve));
        if (process.platform === "win32")
          spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
            stdio: "ignore",
            windowsHide: true,
          });
        else child.kill("SIGKILL");
        let cleanupTimer;
        try {
          await Promise.race([
            closed,
            new Promise((_, reject) => {
              cleanupTimer = setTimeout(
                () =>
                  reject(
                    new Error("Owned runner cleanup did not close its pipes"),
                  ),
                2000,
              );
            }),
          ]);
        } finally {
          clearTimeout(cleanupTimer);
        }
      }
      await new Promise((resolve) => server.close(resolve));
    }
  },
);

test("malformed exact reset URL fails closed rather than throwing before the failure latch", () => {
  const detector = createAcceptanceDetector();
  assert.doesNotThrow(() =>
    detector.observeResponse({
      status: 500,
      method: "POST",
      url: "broken-url",
      testId: mockedTitle,
      mockedResetProof: { fulfilled: true, detail: "Reset failed" },
    }),
  );
  assert.equal(detector.snapshot().failure.kind, "browser-http-5xx");
});

test("a console error on a live200 page latches while exact proven mock-resource error is allowed", async () => {
  const server = createServer((_, response) => {
    response.writeHead(200, { "content-type": "text/html" });
    response.end("<!doctype html><title>Offline fixture</title>");
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch();
  let instrumentation;
  try {
    const detector = createAcceptanceDetector();
    instrumentation = instrumentAcceptanceBrowser(browser, {
      testId: mockedTitle,
      onResponse: (row) => detector.observeResponse(row),
      onPageError: (row) => detector.observePageError(row),
      onConsoleError: (row) => detector.observeConsoleError(row),
    });
    const page = await browser.newPage();
    await page.route("**/api/demo/scenarios/kafka-pricing-lag/reset", (value) =>
      value.fulfill({ status: 500, json: { detail: "Reset failed" } }),
    );
    await page.goto(url);
    await page.evaluate(() =>
      fetch("/api/demo/scenarios/kafka-pricing-lag/reset", {
        method: "POST",
      }).then((response) => response.text()),
    );
    assert.equal(detector.snapshot().failure, null);
    await page.evaluate(() =>
      console.error("Unexpected client error despite HTTP200"),
    );
    assert.equal(detector.snapshot().failure.kind, "browser-console-error");
  } finally {
    instrumentation?.detach();
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});


test("SSE cleanup events are fatal backend failures with split JSON and first failure latch", () => {
  for (const event of ["sse_cleanup_deadline", "sse_cleanup_failed", "sse_read_failed", "sse_shutdown_incomplete"]) {
    const detector = createAcceptanceDetector();
    const line = JSON.stringify({level: "ERROR", logger: "creditops.sse", event}) + "\n";
    detector.feedLog("backend", line.slice(0, 17));
    detector.feedLog("backend", line.slice(17));
    assert.equal(detector.snapshot().failure?.kind, "backend-sse-cleanup");
    assert.equal(detector.snapshot().failure?.event, event);
    detector.feedLog("backend", '"GET /health HTTP/1.1" 503\n');
    assert.equal(detector.snapshot().failure?.event, event);
  }
});
