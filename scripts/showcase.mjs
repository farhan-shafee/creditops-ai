import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

export function createShowcaseEnvironment(parent) {
  const environment = Object.fromEntries(Object.entries(parent).filter(
    ([key]) => !/^(openai_api_key|anthropic_api_key|admin_api_key)$/i.test(key),
  ));
  return {
    ...environment,
    CREDITOPS_ENV_FILE: '',
    PUBLIC_DEMO: 'true',
    EMBEDDINGS_ENABLED: 'false',
    TELEMETRY_MODE: 'persisted',
    DATABASE_REQUIRE_SSL: 'false',
    REPLAY_DIR: join(root, 'data', 'showcase'),
    DATABASE_URL: `sqlite+aiosqlite:///${join(root, 'artifacts', 'runtime', 'showcase.db').replaceAll('\\', '/')}`,
    API_BASE_URL: 'http://127.0.0.1:8000',
    MCP_API_URL: 'http://127.0.0.1:8000',
  };
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  const environment = createShowcaseEnvironment(process.env);
  for (const key of Object.keys(process.env)) delete process.env[key];
  Object.assign(process.env, environment);
  console.log('Selected recorded synthetic examples · keyless public profile · no new model calls during playback');
  await import('./dev.mjs');
}
