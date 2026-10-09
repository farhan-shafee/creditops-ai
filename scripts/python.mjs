import { spawnSync } from 'node:child_process';
import { delimiter, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const result = spawnSync(python, process.argv.slice(2), {
  cwd: root, stdio: 'inherit', windowsHide: true,
  env: { ...process.env, PYTHONPATH: [join(root, 'apps/api'), join(root, 'apps/mcp')].join(delimiter) },
});
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
