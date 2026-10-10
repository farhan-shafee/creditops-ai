import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { delimiter, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const isWindows = process.platform === 'win32';
const python = process.env.PYTHON ?? join(root, '.venv', isWindows ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) {
  console.error('Create the Python environment first: python -m venv .venv, then install .[dev]. See README.');
  process.exit(1);
}

const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (isWindows && child.pid) {
      spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true });
    } else if (child.pid) {
      try { process.kill(-child.pid, 'SIGTERM'); } catch { child.kill('SIGTERM'); }
    }
  }
  process.exitCode = code;
}

function start(command, args, extraEnv = {}) {
  const child = spawn(command, args, {
    cwd: root, stdio: 'inherit', windowsHide: true, detached: !isWindows,
    env: { ...process.env, ...extraEnv },
  });
  children.push(child);
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code ?? 1); });
}

console.log('CreditOps AI: web http://127.0.0.1:3000 · API http://127.0.0.1:8000 · synthetic data only');
start(python, ['-m', 'uvicorn', 'creditops.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'], {
  PYTHONPATH: [join(root, 'apps/api'), join(root, 'apps/mcp')].join(delimiter),
});
start(isWindows ? 'cmd.exe' : 'pnpm', isWindows
  ? ['/d', '/s', '/c', 'pnpm --filter @creditops/web dev']
  : ['--filter', '@creditops/web', 'dev']);
process.on('SIGINT', () => stop(0));
process.on('SIGTERM', () => stop(0));
