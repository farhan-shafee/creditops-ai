import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { delimiter, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const windows = process.platform === 'win32';
const python = join(root, '.venv', windows ? 'Scripts/python.exe' : 'bin/python');
const mode = process.argv[2];
if (!['test', 'lint'].includes(mode)) {
  console.error('Usage: node scripts/check.mjs test|lint');
  process.exit(2);
}
if (!existsSync(python)) {
  console.error('Create .venv and install the root Python project with its dev dependencies first. See README.');
  process.exit(1);
}
mkdirSync(join(root, 'artifacts', 'test-tmp'), { recursive: true });
const pythonArgs = mode === 'test'
  ? ['-m', 'pytest', '--basetemp', `artifacts/test-tmp/root-check-${process.pid}`]
  : ['-m', 'ruff', 'check', 'apps', 'scripts'];
const pnpmCommand = windows ? 'cmd.exe' : 'pnpm';
const pnpmArgs = windows ? ['/d', '/s', '/c', `pnpm --filter @creditops/web ${mode}`] : ['--filter', '@creditops/web', mode];
const checks = [[python, pythonArgs]];
if (mode === 'test') checks.push([process.execPath, ['--test', 'scripts/check-lint-dependencies.mjs']]);
checks.push([pnpmCommand, pnpmArgs]);
for (const [command, args] of checks) {
  const result = spawnSync(command, args, {
    cwd: root, stdio: 'inherit', windowsHide: true,
    env: { ...process.env, PYTHONPATH: [join(root, 'apps/api'), join(root, 'apps/mcp')].join(delimiter) },
  });
  if (result.error) console.error(result.error.message);
  if (result.status !== 0) process.exit(result.status ?? 1);
}
