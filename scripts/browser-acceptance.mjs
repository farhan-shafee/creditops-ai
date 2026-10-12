import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync, appendFileSync, writeFileSync, existsSync, readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { randomUUID, createHash } from 'node:crypto';
import { createAcceptanceDetector } from './acceptance-detector.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
function clean(text) {
  return String(text).replace(/([a-z][a-z0-9+.-]*:\/\/)[^\s/:@]+:[^\s@]+@/gi, '$1[REDACTED]@').replace(/Bearer\s+[a-z0-9._~+/=-]+/gi, 'Bearer [REDACTED]').replace(/\bsk-[A-Za-z0-9_-]{8,}/g, '[REDACTED]');
}

// One supervisor for the existing Playwright/server lifecycle. Completion means
// child close AND final output drain; an exit-zero suite cannot clear a failure.
export async function runAcceptance({ command, args, directory, cwd = root, env = process.env, forwardOutput = true, drainTimeoutMs = 15000, source = null }) {
  if (!Number.isFinite(drainTimeoutMs) || drainTimeoutMs <= 0 || drainTimeoutMs > 15000) throw new Error("Final drain must have a finite allowance no greater than 15 seconds");
  directory = resolve(directory);
  if (existsSync(directory)) throw new Error('Preserve existing acceptance output; choose a fresh result directory');
  mkdirSync(directory, { recursive: true });
  const failureFile = join(directory, 'acceptance-failure.json');
  const startedAt = new Date().toISOString();
  const environment = { ...env, ACCEPTANCE_RESULT_DIR: directory, CREDITOPS_ENV_FILE: '', OPENAI_API_KEY: '', ANTHROPIC_API_KEY: '', ADMIN_API_KEY: '', PLAYWRIGHT_HTML_OUTPUT_DIR: join(directory, 'html'), PLAYWRIGHT_JSON_OUTPUT_FILE: join(directory, 'playwright.json'), PLAYWRIGHT_HTML_OPEN: 'never' };
  let child, stopTimer, drainTimer, drainExpired = false, containment = null, spawnError = null, suiteExitCode = null, suiteExitSignal = null, exitedAt = null;
  const detector = createAcceptanceDetector({ onFailure: failure => {
    if (!existsSync(failureFile)) writeFileSync(failureFile, JSON.stringify(failure, null, 2), { flag: 'wx' });
    detector.markStopStarted();
    if (child?.connected) child.send({ type: 'acceptance-stop' }, () => {});
    // Existing harness allowance. This is failed-run containment, not application cleanup.
    stopTimer ??= setTimeout(() => {
      if (child?.exitCode === null) {
        spawnError ??= 'Acceptance runner did not finish its owned stop within 15 seconds';
        child.kill('SIGTERM');
      }
    }, 15000);
  }});
  const signalHandlers = new Map(['SIGINT', 'SIGTERM'].map(signal => [signal, () => detector.observeFailure({ kind: 'external-interruption', signal })]));
  for (const [signal, handler] of signalHandlers) process.on(signal, handler);
  const tails = new Map();
  const logs = new Map(['stdout', 'stderr'].map(stream => [stream, join(directory, `${stream}.log`)]));
  for (const file of logs.values()) writeFileSync(file, '', { flag: 'wx' });
  function inspectLine(stream, line) {
    // UI assertion/retry output is not application-server output.
    if (line.includes("[WebServer]")) {
      detector.feedLog(`backend:${stream}`, line + "\n");
      detector.feedLog(`frontend:${stream}`, line + "\n");
    }
    const offset = line.indexOf('ACCEPTANCE_FAILURE ');
    if (offset >= 0) {
      try { detector.observeFailure(JSON.parse(line.slice(offset + 19))); }
      catch (error) { if (!(error instanceof SyntaxError)) throw error; }
    }
  }
  function receive(stream, chunk) {
    const text = clean(chunk);
    appendFileSync(logs.get(stream), text);
    if (forwardOutput) (stream === 'stdout' ? process.stdout : process.stderr).write(text);
    // Playwright prefixes both backend and frontend output with [WebServer].

    const lines = (tails.get(stream) ?? '') + text;
    const parts = lines.split('\n');
    tails.set(stream, parts.pop());
    parts.forEach(line => inspectLine(stream, line));
    if (tails.get(stream)) inspectLine(stream, tails.get(stream));
  }
  child = spawn(command, args, { cwd, env: environment, windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
  child.stdout.on('data', chunk => receive('stdout', chunk));
  child.stderr.on('data', chunk => receive('stderr', chunk));
  child.once('error', error => { spawnError = clean(error.message); });
  child.once('exit', (code, signal) => {
    suiteExitCode = code; suiteExitSignal = signal; exitedAt = new Date().toISOString();
    drainTimer = setTimeout(() => {
      drainExpired = true;
      detector.observeFailure({ kind: 'owned-output-drain-deadline' });
      // This group was created by this supervisor. Never signal an unrelated PID.
      if (process.platform !== 'win32') {
        try { process.kill(-child.pid, 'SIGTERM'); containment = 'failed-harness-owned-group-SIGTERM'; }
        catch (error) { containment = 'owned-group-unavailable:' + error.code; }
      } else containment = 'incomplete-Windows-descendant-ownership; no unverified PID signalled';
      // Own reader disposal bounds supervisor waiting, not physical resource joining.
      child.stdout.destroy(); child.stderr.destroy();
    }, drainTimeoutMs);
  });
  await new Promise(resolveClosed => child.once('close', resolveClosed));
  for (const [signal, handler] of signalHandlers) process.off(signal, handler);
  const closedAt = new Date().toISOString();
  for (const stream of ['stdout', 'stderr']) {
    detector.flush(`backend:${stream}`);
    detector.flush(`frontend:${stream}`);
    if (tails.get(stream)) inspectLine(stream, tails.get(stream));
  }
  const finalLogDrainAt = new Date().toISOString();
  clearTimeout(stopTimer);
  clearTimeout(drainTimer);
  // Persisted fixture failure remains authoritative even if its IPC line was lost.
  if (existsSync(failureFile)) detector.observeFailure(JSON.parse(readFileSync(failureFile, 'utf8')));
  detector.markStopped();
  const result = { source, startedAt, exitedAt, closedAt, finalLogDrainAt: drainExpired ? null : finalLogDrainAt, finalLogDrainCompleted: !drainExpired, containment, suiteExitCode, suiteExitSignal, spawnError, detector: detector.snapshot(), exitCode: suiteExitCode === 0 && !spawnError && !detector.snapshot().failure ? 0 : 1, node: process.version };
  writeFileSync(join(directory, 'result.json'), JSON.stringify(result, null, 2), { flag: 'wx' });
  return result;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const [profile, ...remaining] = process.argv.slice(2);
  if (!['legacy', 'showcase'].includes(profile)) throw new Error('Select the existing legacy or showcase browser profile');
  const index = remaining.indexOf('--result-dir');
  const directory = index < 0 ? join(root, 'artifacts/test-tmp/browser-acceptance', `${profile}-${randomUUID()}`) : resolve(remaining.splice(index, 2)[1]);
  const requireWeb = createRequire(join(root, 'apps/web/package.json'));
  const requireTest = createRequire(requireWeb.resolve('@playwright/test'));
  const packagePath = requireTest.resolve('playwright/package.json');
  const cli = join(dirname(packagePath), 'cli.js');
  const config = profile === 'showcase' ? ['--config=playwright.showcase.config.ts'] : [];
  const git = (...args) => execFileSync('git', ['-C', root, ...args], { encoding: 'utf8' }).trim();
  const source = { head: git('rev-parse', 'HEAD'), branch: git('branch', '--show-current'), files: {} };
  for (const relative of git('ls-files', '--cached', '--others', '--exclude-standard', '-z').split('\0').filter(Boolean)) source.files[relative] = createHash('sha256').update(readFileSync(join(root, relative))).digest('hex');
  const result = await runAcceptance({ source, command: process.execPath, args: ['--import', pathToFileURL(join(root, 'scripts/acceptance-stop.mjs')).href, cli, 'test', ...config, ...remaining, '--reporter=list,html,json', '--output='+join(directory, 'test-results')], directory, cwd: join(root, 'apps/web') });
  console.log('ACCEPTANCE_RESULT '+JSON.stringify({ exitCode: result.exitCode, suiteExitCode: result.suiteExitCode, failure: result.detector.failure, directory }));
  process.exitCode = result.exitCode;
}
