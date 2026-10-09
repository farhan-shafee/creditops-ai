import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const webRoot = path.join(root, 'apps/web');
const web = createRequire(path.join(webRoot, 'package.json'));
const nextConfig = createRequire(web.resolve('eslint-config-next'));
const pluginEntry = nextConfig.resolve('@next/eslint-plugin-next');
const plugin = createRequire(pluginEntry);
const { getRootDirs } = plugin('./utils/get-root-dirs.js');

// Guard the scoped replacement's actual use in Next's lint plugin, including
// the literal-directory expansion difference between fast-glob and tinyglobby.
test('Next root discovery retains literal, glob, brace, array and absolute semantics', () => {
  const prior = process.cwd();
  process.chdir(root);
  try {
    for (const [rootDir, expected] of [
      ['apps/web', ['apps/web']],
      ['apps/*', ['apps/api', 'apps/mcp', 'apps/web']],
      ['apps/{web,api}', ['apps/api', 'apps/web']],
      ['apps/nonexistent', []],
      [['apps/web', 'apps/api'], ['apps/api', 'apps/web']],
      [webRoot, [webRoot]],
      [root, [root]],
      ['.', [root]],
    ]) {
      const actual = getRootDirs({ cwd: root, settings: { next: { rootDir } } });
      assert.deepEqual(
        actual.map((directory) => path.resolve(directory)).sort(),
        expected.map((directory) => path.resolve(directory)).sort(),
      );
    }
    assert.equal(plugin('fast-glob/package.json').name, 'tinyglobby');
  } finally {
    process.chdir(prior);
  }
});

test('Next lint rules still report a deliberately invalid image element', async () => {
  const prior = process.cwd();
  process.chdir(webRoot);
  try {
    const { ESLint } = web('eslint');
    const eslint = new ESLint({
      cwd: webRoot,
      overrideConfig: { settings: { next: { rootDir: webRoot } } },
    });
    const [result] = await eslint.lintText(
      "export default function Page() { return <img src='/synthetic.png' alt='Synthetic' />; }",
      { filePath: 'src/app/dependency-check.tsx' },
    );
    assert.ok(result.messages.some((message) => message.ruleId === '@next/next/no-img-element'));
  } finally {
    process.chdir(prior);
  }
});
