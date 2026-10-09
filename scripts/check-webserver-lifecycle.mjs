import assert from "node:assert/strict";
import {
  copyFile,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import { performance } from "node:perf_hooks";
import { test } from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

async function within(promise, timeout, message) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(message)), timeout);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

async function running(pid) {
  try {
    // An orphan zombie has already exited; it cannot retain an output pipe.
    const stat = await readFile(`/proc/${pid}/stat`, "utf8");
    return !/\) Z /.test(stat);
  } catch (error) {
    if (error.code === "ENOENT") return false;
    throw error;
  }
}

test(
  "Playwright closes inherited pipes and all detached Linux development children",
  {
    skip:
      process.platform !== "linux" &&
      "Unix process-group proof runs in Linux CI; Windows uses taskkill tree cleanup.",
    timeout: 15_000,
  },
  async (context) => {
    const web = createRequire(path.join(root, "apps/web/package.json"));
    const testPackage = createRequire(web.resolve("@playwright/test"));
    const playwright = createRequire(
      testPackage.resolve("playwright/package.json"),
    );
    // Exercise the pinned runner's real plugin and TypeScript config loader,
    // including its process-group signals and wait for inherited pipe closure.
    const { transform } = playwright("playwright/lib/common");
    const { webServer } = playwright("playwright/lib/runner");
    const loaded = await transform.requireOrImport(
      path.join(root, "apps/web/playwright.config.ts"),
    );
    const options = loaded.default.webServer;
    assert.ok(
      options && !Array.isArray(options),
      "Lifecycle test needs the configured owned web server",
    );
    const fixture = await mkdtemp(
      path.join(os.tmpdir(), "creditops-lifecycle-"),
    );
    let output = "";
    let teardown;
    let plugin;
    const childPids = () => [
      ...new Set(
        [...output.matchAll(/LIFECYCLE_STUB_PID=(\d+)/g)].map((match) =>
          Number(match[1]),
        ),
      ),
    ];
    try {
      await Promise.all([
        mkdir(path.join(fixture, "scripts")),
        mkdir(path.join(fixture, ".venv/bin"), { recursive: true }),
        mkdir(path.join(fixture, "bin")),
      ]);
      await copyFile(
        path.join(root, "scripts/dev.mjs"),
        path.join(fixture, "scripts/dev.mjs"),
      );
      const stub = `#!/usr/bin/env node
import { spawn } from 'node:child_process';
console.log('LIFECYCLE_STUB_PID=' + process.pid);
spawn(process.execPath, ['-e', "console.log('LIFECYCLE_STUB_PID=' + process.pid); setInterval(() => {}, 1000)"], { stdio: 'inherit' });
setInterval(() => {}, 1000);
`;
      await Promise.all([
        writeFile(path.join(fixture, ".venv/bin/python"), stub, {
          mode: 0o755,
        }),
        writeFile(path.join(fixture, "bin/pnpm"), stub, { mode: 0o755 }),
      ]);
      const quote = (value) => `'${value.replaceAll("'", "'\\''")}'`;
      plugin = webServer({
        ...options,
        command: `${quote(process.execPath)} ${quote(path.join(fixture, "scripts/dev.mjs"))}`,
        cwd: fixture,
        url: undefined,
        wait: { stdout: /LIFECYCLE_STUB_PID=/ },
        timeout: 3000,
        reuseExistingServer: false,
        env: {
          ...options.env,
          PATH: `${path.join(fixture, "bin")}:${process.env.PATH}`,
        },
        stdout: "pipe",
        stderr: "pipe",
      });
      const capture = (chunk) => {
        output += chunk.toString();
      };
      await plugin.setup({}, fixture, { onStdOut: capture, onStdErr: capture });
      await within(
        (async () => {
          while (childPids().length !== 4) await delay(20);
        })(),
        3000,
        `Controlled development children did not start: ${output}`,
      );
      const started = performance.now();
      teardown = plugin.teardown();
      await within(
        teardown,
        3000,
        "Playwright teardown hung: detached children retain inherited stdout/stderr pipes",
      );
      await delay(40);
      const survivors = [];
      for (const pid of childPids())
        if (await running(pid)) survivors.push(pid);
      assert.deepEqual(
        survivors,
        [],
        "No controlled API, web or descendant process may survive teardown",
      );
      context.diagnostic(
        `Real Playwright teardown closed inherited pipes in ${(performance.now() - started).toFixed(1)} ms; ${childPids().length} controlled children stopped.`,
      );
    } finally {
      const survivors = [];
      for (const pid of childPids()) {
        if (await running(pid)) {
          survivors.push(pid);
          try {
            process.kill(pid, "SIGKILL");
          } catch (error) {
            if (error.code !== "ESRCH") throw error;
          }
        }
      }
      if (survivors.length)
        context.diagnostic(
          `Failure cleanup terminated owned surviving fixture PIDs: ${survivors.join(", ")}`,
        );
      if (teardown)
        await within(teardown, 2000, "Fixture pipe cleanup did not finish");
      else if (plugin)
        await within(
          plugin.teardown(),
          2000,
          "Fixture startup cleanup did not finish",
        );
      await rm(fixture, { recursive: true, force: true });
    }
  },
);
