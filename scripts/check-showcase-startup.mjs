import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

test('showcase child profile drops inherited canary credentials and owner storage', async () => {
  const modulePath = new URL('./showcase.mjs', import.meta.url);
  const exists = spawnSync(process.execPath, ['--input-type=module', '-e',
    `const module = await import(${JSON.stringify(modulePath.href)}); process.exit(typeof module.createShowcaseEnvironment === 'function' ? 0 : 1);`],
  { encoding: 'utf8', timeout: 5_000 });
  assert.equal(exists.status, 0, 'the keyless showcase profile must be available without starting servers');
  const { createShowcaseEnvironment } = await import(modulePath.href);
  const parent = {
    PATH: 'inherited-runtime-path',
    OPENAI_API_KEY: 'offline-openai-canary',
    anthropic_api_key: 'offline-anthropic-canary',
    Admin_Api_Key: 'offline-admin-canary',
    CREDITOPS_ENV_FILE: join(root, '.env'),
    PUBLIC_DEMO: 'false',
    EMBEDDINGS_ENABLED: 'true',
    TELEMETRY_MODE: 'kafka',
    REPLAY_DIR: join(root, 'artifacts', 'live-verification'),
    DATABASE_URL: 'sqlite+aiosqlite:///owner.db',
    API_BASE_URL: 'https://unrelated-api.invalid',
  };
  const profile = createShowcaseEnvironment(parent);
  assert.equal(parent.OPENAI_API_KEY, 'offline-openai-canary', 'the parent environment stays intact');
  assert.equal(profile.PATH, parent.PATH, 'local runtime discovery stays available');
  assert.ok(Object.keys(profile).every(key => !/^(openai_api_key|anthropic_api_key|admin_api_key)$/i.test(key)));
  assert.equal(profile.CREDITOPS_ENV_FILE, '');
  assert.equal(profile.PUBLIC_DEMO, 'true');
  assert.equal(profile.EMBEDDINGS_ENABLED, 'false');
  assert.equal(profile.TELEMETRY_MODE, 'persisted');
  assert.equal(profile.REPLAY_DIR, join(root, 'data', 'showcase'));
  assert.equal(profile.DATABASE_URL, `sqlite+aiosqlite:///${join(root, 'artifacts', 'runtime', 'showcase.db').replaceAll('\\', '/')}`);
  assert.equal(profile.API_BASE_URL, 'http://127.0.0.1:8000');
});
